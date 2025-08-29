"""
Unit tests for the USAJOBS ETL Service

These tests focus on individual components and their behavior in isolation.
"""
import json
from datetime import date, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from etl.etl import CircuitBreaker, DatabaseManager, JobPosting, USAJobsAPIClient, retry


class TestJobPosting:
    """Unit tests for JobPosting data class."""

    def test_job_posting_creation(self):
        """Test creating a JobPosting instance."""
        job = JobPosting(
            position_title="Data Engineer",
            position_uri="https://example.com/job/123",
            position_location="Washington, DC",
            position_remuneration="$80,000 - $120,000",
        )

        assert job.position_title == "Data Engineer"
        assert job.position_uri == "https://example.com/job/123"
        assert job.position_location == "Washington, DC"
        assert job.position_remuneration == "$80,000 - $120,000"
        assert isinstance(job.extracted_at, datetime)

    def test_job_posting_validation_valid(self):
        """Test validation of valid job posting."""
        job = JobPosting(
            position_title="Data Engineer",
            position_uri="https://example.com/job/123",
            position_location="Washington, DC",
            position_remuneration="$80,000",
        )

        assert job.validate() is True

    def test_job_posting_validation_invalid_title(self):
        """Test validation with invalid title."""
        job = JobPosting(
            position_title="",
            position_uri="https://example.com/job/123",
            position_location="Washington, DC",
            position_remuneration="$80,000",
        )

        assert job.validate() is False

    def test_job_posting_validation_invalid_uri(self):
        """Test validation with invalid URI."""
        job = JobPosting(
            position_title="Data Engineer",
            position_uri="invalid-uri",
            position_location="Washington, DC",
            position_remuneration="$80,000",
        )

        assert job.validate() is False

    def test_job_posting_to_dict(self):
        """Test converting job posting to dictionary."""
        job = JobPosting(
            position_title="Data Engineer",
            position_uri="https://example.com/job/123",
            position_location="Washington, DC",
            position_remuneration="$80,000",
        )

        job_dict = job.to_dict()
        assert isinstance(job_dict, dict)
        assert job_dict["position_title"] == "Data Engineer"
        assert job_dict["position_uri"] == "https://example.com/job/123"


class TestCircuitBreaker:
    """Unit tests for CircuitBreaker."""

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        cb = CircuitBreaker(failure_threshold=3)

        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == "CLOSED"

    def test_circuit_breaker_open_after_failures(self):
        """Test circuit breaker opens after failures."""
        cb = CircuitBreaker(failure_threshold=2)

        def failing_func():
            raise Exception("API Error")

        # First failure
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == "CLOSED"

        # Second failure should open the circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == "OPEN"

        # Third call should fail immediately
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            cb.call(failing_func)


class TestUSAJobsAPIClient:
    """Unit tests for USAJobsAPIClient."""

    def test_client_initialization(self):
        """Test API client initialization."""
        client = USAJobsAPIClient("test_key")

        assert client.api_key == "test_key"
        assert client.base_url == "https://data.usajobs.gov/api/search"
        assert "Authorization-Key" in client.session.headers
        assert client.session.headers["Authorization-Key"] == "test_key"

    @patch("time.sleep")
    def test_search_jobs_success(self, mock_sleep, mock_api_response, mock_successful_response):
        """Test successful job search."""
        client = USAJobsAPIClient("test_key")
        mock_successful_response.json.return_value = mock_api_response

        with patch.object(client.session, "get", return_value=mock_successful_response):
            result = client.search_jobs("data engineering")

        assert result == mock_api_response
        mock_sleep.assert_called_once_with(1.5)  # Rate limiting

    def test_search_jobs_with_location(self, mock_api_response, mock_successful_response):
        """Test job search with location parameter."""
        client = USAJobsAPIClient("test_key")
        mock_successful_response.json.return_value = mock_api_response

        with patch.object(client.session, "get", return_value=mock_successful_response) as mock_get:
            with patch("time.sleep"):
                client.search_jobs("data engineering", location="Chicago")

        # Verify location was included in parameters
        call_args = mock_get.call_args
        assert "LocationName" in call_args[1]["params"]
        assert call_args[1]["params"]["LocationName"] == "Chicago"

    def test_search_jobs_api_failure(self, mock_failed_response):
        """Test API failure handling."""
        client = USAJobsAPIClient("test_key")

        with patch.object(client.session, "get", return_value=mock_failed_response):
            with pytest.raises(requests.HTTPError):
                client.search_jobs("data engineering")

    def test_extract_job_data_success(self, api_client, mock_api_response):
        """Test successful job data extraction."""
        jobs = api_client.extract_job_data(mock_api_response)

        assert len(jobs) == 2
        assert all(isinstance(job, JobPosting) for job in jobs)
        assert jobs[0].position_title == "Data Engineer"
        assert jobs[1].position_title == "Senior Data Engineer"

    def test_extract_job_data_empty_response(self, api_client, mock_empty_api_response):
        """Test extraction from empty response."""
        jobs = api_client.extract_job_data(mock_empty_api_response)
        assert len(jobs) == 0

    def test_extract_job_data_invalid_response(self, api_client):
        """Test extraction from invalid response."""
        invalid_response = {"InvalidKey": "InvalidValue"}
        jobs = api_client.extract_job_data(invalid_response)
        assert len(jobs) == 0

    def test_parse_location_single_location(self, api_client):
        """Test location parsing with single location."""
        location_data = [{"CityName": "Washington", "StateCode": "DC", "CountryCode": "US"}]
        result = api_client._parse_location(location_data)
        assert result == "Washington, DC, US"

    def test_parse_location_empty_data(self, api_client):
        """Test location parsing with empty data."""
        result = api_client._parse_location([])
        assert result == "Location not specified"

        result = api_client._parse_location(None)
        assert result == "Location not specified"

    def test_parse_remuneration_with_range(self, api_client):
        """Test remuneration parsing with salary range."""
        remuneration_data = [
            {"MinimumRange": "80000", "MaximumRange": "120000", "RateIntervalCode": "Per Year"}
        ]
        result = api_client._parse_remuneration(remuneration_data)
        assert result == "$80,000 - $120,000 Per Year"

    def test_parse_remuneration_minimum_only(self, api_client):
        """Test remuneration parsing with minimum only."""
        remuneration_data = [{"MinimumRange": "80000", "RateIntervalCode": "Per Year"}]
        result = api_client._parse_remuneration(remuneration_data)
        assert result == "$80,000+ Per Year"

    def test_parse_remuneration_empty_data(self, api_client):
        """Test remuneration parsing with empty data."""
        result = api_client._parse_remuneration([])
        assert result == "Not specified"

    def test_parse_date_valid_iso(self, api_client):
        """Test date parsing with valid ISO string."""
        date_string = "2023-01-01T00:00:00.0000000"
        result = api_client._parse_date(date_string)
        assert result == date(2023, 1, 1)

    def test_parse_date_invalid(self, api_client):
        """Test date parsing with invalid string."""
        result = api_client._parse_date("invalid-date")
        assert result is None

        result = api_client._parse_date(None)
        assert result is None


class TestDatabaseManager:
    """Unit tests for DatabaseManager."""

    def test_database_manager_initialization(self):
        """Test database manager initialization."""
        db_manager = DatabaseManager(
            host="localhost", port="5432", dbname="test", user="user", password="pass"
        )

        assert db_manager.connection_params["host"] == "localhost"
        assert db_manager.connection_params["port"] == "5432"
        assert db_manager.connection_params["dbname"] == "test"
        assert db_manager.connection_params["user"] == "user"
        assert db_manager.connection_params["password"] == "pass"


class TestRetryDecorator:
    """Unit tests for retry decorator."""

    def test_retry_success_on_first_attempt(self):
        """Test retry decorator with successful first attempt."""

        @retry(max_attempts=3)
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

    def test_retry_success_after_failures(self):
        """Test retry decorator with success after failures."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_retry_max_attempts_exceeded(self):
        """Test retry decorator when max attempts are exceeded."""

        @retry(max_attempts=2, delay=0.01)
        def failing_func():
            raise Exception("Persistent failure")

        with pytest.raises(Exception, match="Persistent failure"):
            failing_func()


class TestDataValidation:
    """Unit tests for data validation."""

    def test_job_posting_with_optional_fields(self):
        """Test job posting creation with optional fields."""
        job = JobPosting(
            position_title="Data Engineer",
            position_uri="https://example.com/job/123",
            position_location="Washington, DC",
            position_remuneration="$80,000",
            organization_name="DOD",
            department_name="DISA",
            job_category="IT",
            job_grade="GS-13",
            position_start_date=date(2023, 1, 1),
            position_end_date=date(2023, 12, 31),
        )

        assert job.organization_name == "DOD"
        assert job.department_name == "DISA"
        assert job.job_category == "IT"
        assert job.job_grade == "GS-13"
        assert job.position_start_date == date(2023, 1, 1)
        assert job.position_end_date == date(2023, 12, 31)

    def test_job_posting_none_optional_fields(self):
        """Test job posting with None optional fields."""
        job = JobPosting(
            position_title="Data Engineer",
            position_uri="https://example.com/job/123",
            position_location="Washington, DC",
            position_remuneration="$80,000",
            organization_name=None,
            department_name=None,
        )

        assert job.organization_name is None
        assert job.department_name is None
