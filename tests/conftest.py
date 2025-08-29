# Test configuration and fixtures
import json
import os

# Import the main ETL components
import sys
import time
from datetime import datetime
from typing import Any, Dict, Generator
from unittest.mock import Mock, patch

import docker
import psycopg2
import pytest
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from etl.etl import DatabaseManager, ETLService, JobPosting, USAJobsAPIClient

# Test configuration
TEST_DB_NAME = "usajobs_test"
TEST_DB_USER = "postgres"
TEST_DB_PASSWORD = "test_password"
TEST_DB_PORT = 5433  # Use different port to avoid conflicts
TEST_DB_HOST = "localhost"


@pytest.fixture(scope="session")
def docker_client():
    """Provide a Docker client for managing test containers."""
    return docker.from_env()


@pytest.fixture(scope="session")
def test_database_container(docker_client):
    """Create and manage a PostgreSQL test container."""
    container_name = f"test-postgres-{int(time.time())}"

    # Remove existing container if it exists
    try:
        existing = docker_client.containers.get(container_name)
        existing.remove(force=True)
    except docker.errors.NotFound:
        pass

    # Start PostgreSQL container
    container = docker_client.containers.run(
        "postgres:15",
        name=container_name,
        environment={
            "POSTGRES_DB": TEST_DB_NAME,
            "POSTGRES_USER": TEST_DB_USER,
            "POSTGRES_PASSWORD": TEST_DB_PASSWORD,
        },
        ports={"5432/tcp": TEST_DB_PORT},
        detach=True,
        remove=True,
    )

    # Wait for PostgreSQL to be ready
    max_retries = 30
    for _ in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=TEST_DB_HOST,
                port=TEST_DB_PORT,
                dbname=TEST_DB_NAME,
                user=TEST_DB_USER,
                password=TEST_DB_PASSWORD,
            )
            conn.close()
            break
        except psycopg2.OperationalError:
            time.sleep(1)
    else:
        pytest.fail("PostgreSQL container failed to start within timeout")

    yield container

    # Cleanup
    container.stop()


@pytest.fixture
def test_db_connection(test_database_container):
    """Provide a database connection for testing."""
    conn = psycopg2.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        dbname=TEST_DB_NAME,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
    )

    yield conn

    # Cleanup
    conn.close()


@pytest.fixture
def database_manager(test_database_container):
    """Database manager instance for testing."""
    return DatabaseManager(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        dbname=TEST_DB_NAME,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
    )


@pytest.fixture
def clean_database(database_manager):
    """Ensure clean database state for each test."""
    # Setup: Create tables
    database_manager.create_tables()

    yield database_manager

    # Teardown: Clean up tables
    with database_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS job_postings CASCADE;")
            cur.execute("DROP TABLE IF EXISTS etl_metadata CASCADE;")
            cur.execute("DROP VIEW IF EXISTS recent_job_postings CASCADE;")
            cur.execute("DROP VIEW IF EXISTS job_statistics CASCADE;")
            conn.commit()


@pytest.fixture
def mock_api_response():
    """Mock USAJOBS API response data."""
    return {
        "SearchResult": {
            "SearchResultCount": 2,
            "SearchResultCountAll": 100,
            "SearchResultItems": [
                {
                    "MatchedObjectDescriptor": {
                        "PositionTitle": "Data Engineer",
                        "PositionURI": "https://www.usajobs.gov/job/12345",
                        "PositionLocation": [
                            {"CityName": "Washington", "StateCode": "DC", "CountryCode": "US"}
                        ],
                        "PositionRemuneration": [
                            {
                                "MinimumRange": "80000",
                                "MaximumRange": "120000",
                                "RateIntervalCode": "Per Year",
                            }
                        ],
                        "OrganizationName": "Department of Defense",
                        "DepartmentName": "Defense Information Systems Agency",
                        "PositionStartDate": "2023-01-01T00:00:00.0000000",
                        "PositionEndDate": "2023-12-31T00:00:00.0000000",
                        "JobCategory": [{"Name": "Information Technology"}],
                        "JobGrade": [{"Code": "GS-13"}],
                    }
                },
                {
                    "MatchedObjectDescriptor": {
                        "PositionTitle": "Senior Data Engineer",
                        "PositionURI": "https://www.usajobs.gov/job/67890",
                        "PositionLocation": [
                            {"CityName": "Chicago", "StateCode": "IL", "CountryCode": "US"}
                        ],
                        "PositionRemuneration": [
                            {
                                "MinimumRange": "95000",
                                "MaximumRange": "140000",
                                "RateIntervalCode": "Per Year",
                            }
                        ],
                        "OrganizationName": "Department of Transportation",
                        "DepartmentName": "Federal Aviation Administration",
                    }
                },
            ],
        }
    }


@pytest.fixture
def mock_empty_api_response():
    """Mock empty USAJOBS API response."""
    return {
        "SearchResult": {"SearchResultCount": 0, "SearchResultCountAll": 0, "SearchResultItems": []}
    }


@pytest.fixture
def api_client():
    """API client instance for testing."""
    return USAJobsAPIClient(api_key="test_api_key")


@pytest.fixture
def sample_job_postings():
    """Sample job posting data for testing."""
    return [
        JobPosting(
            position_title="Data Engineer",
            position_uri="https://www.usajobs.gov/job/12345",
            position_location="Washington, DC, US",
            position_remuneration="$80,000 - $120,000 Per Year",
            organization_name="Department of Defense",
            department_name="Defense Information Systems Agency",
            job_category="Information Technology",
            job_grade="GS-13",
        ),
        JobPosting(
            position_title="Senior Data Engineer",
            position_uri="https://www.usajobs.gov/job/67890",
            position_location="Chicago, IL, US",
            position_remuneration="$95,000 - $140,000 Per Year",
            organization_name="Department of Transportation",
            department_name="Federal Aviation Administration",
        ),
    ]


@pytest.fixture
def mock_requests_session():
    """Mock requests session for API testing."""
    session = Mock()
    session.get = Mock()
    return session


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    original_env = {}

    # Store original values
    test_env_vars = [
        "USAJOBS_API_KEY",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "LOG_LEVEL",
    ]

    for var in test_env_vars:
        original_env[var] = os.environ.get(var)

    # Set test values
    os.environ.update(
        {
            "USAJOBS_API_KEY": "test_api_key",
            "POSTGRES_HOST": TEST_DB_HOST,
            "POSTGRES_PORT": str(TEST_DB_PORT),
            "POSTGRES_DB": TEST_DB_NAME,
            "POSTGRES_USER": TEST_DB_USER,
            "POSTGRES_PASSWORD": TEST_DB_PASSWORD,
            "LOG_LEVEL": "DEBUG",
        }
    )

    yield

    # Restore original values
    for var, value in original_env.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value


@pytest.fixture
def etl_service(test_database_container):
    """ETL service instance for integration testing."""
    return ETLService()


# Utility fixtures for testing


@pytest.fixture
def mock_successful_response():
    """Mock successful HTTP response."""
    response = Mock()
    response.status_code = 200
    response.raise_for_status = Mock()
    response.json = Mock()
    return response


@pytest.fixture
def mock_failed_response():
    """Mock failed HTTP response."""
    response = Mock()
    response.status_code = 500
    response.raise_for_status = Mock(side_effect=requests.HTTPError("API Error"))
    return response
