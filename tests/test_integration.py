"""
Integration tests for the USAJOBS ETL Service

These tests verify the interaction between components and external systems.
"""
import time
from datetime import date, datetime
from unittest.mock import Mock, patch

import psycopg2
import pytest
import requests

from etl.etl import ETLService, JobPosting


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    def test_database_schema_creation(self, clean_database):
        """Test database schema creation."""
        db_manager = clean_database

        # Verify tables exist
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Check job_postings table
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'job_postings'
                    );
                """
                )
                assert cur.fetchone()[0] is True

                # Check table structure
                cur.execute(
                    """
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'job_postings'
                    ORDER BY ordinal_position;
                """
                )
                columns = cur.fetchall()

                column_names = [col[0] for col in columns]
                expected_columns = [
                    "id",
                    "position_title",
                    "position_uri",
                    "position_location",
                    "position_remuneration",
                    "position_start_date",
                    "position_end_date",
                    "organization_name",
                    "department_name",
                    "job_category",
                    "job_grade",
                    "extracted_at",
                    "created_at",
                    "updated_at",
                ]

                for expected_col in expected_columns:
                    assert expected_col in column_names

    def test_job_insertion(self, clean_database, sample_job_postings):
        """Test inserting job postings into database."""
        db_manager = clean_database

        # Insert jobs
        stats = db_manager.upsert_jobs(sample_job_postings)

        assert stats["inserted"] == 2
        assert stats["updated"] == 0
        assert stats["total"] == 2

        # Verify data was inserted
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM job_postings;")
                count = cur.fetchone()[0]
                assert count == 2

                # Verify specific job data
                cur.execute(
                    """
                    SELECT position_title, position_uri, organization_name 
                    FROM job_postings 
                    ORDER BY position_title;
                """
                )
                jobs = cur.fetchall()

                assert jobs[0][0] == "Data Engineer"
                assert jobs[0][1] == "https://www.usajobs.gov/job/12345"
                assert jobs[0][2] == "Department of Defense"

                assert jobs[1][0] == "Senior Data Engineer"
                assert jobs[1][1] == "https://www.usajobs.gov/job/67890"
                assert jobs[1][2] == "Department of Transportation"

    def test_job_upsert_update(self, clean_database):
        """Test updating existing job postings."""
        db_manager = clean_database

        # Insert initial job
        initial_job = JobPosting(
            position_title="Data Engineer",
            position_uri="https://www.usajobs.gov/job/12345",
            position_location="Washington, DC",
            position_remuneration="$80,000",
        )

        stats1 = db_manager.upsert_jobs([initial_job])
        assert stats1["inserted"] == 1
        assert stats1["updated"] == 0

        # Update the job
        updated_job = JobPosting(
            position_title="Senior Data Engineer",  # Updated title
            position_uri="https://www.usajobs.gov/job/12345",  # Same URI
            position_location="Washington, DC",
            position_remuneration="$90,000",  # Updated salary
        )

        stats2 = db_manager.upsert_jobs([updated_job])
        assert stats2["inserted"] == 0
        assert stats2["updated"] == 1

        # Verify update
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM job_postings;")
                assert cur.fetchone()[0] == 1  # Still only one job

                cur.execute(
                    """
                    SELECT position_title, position_remuneration 
                    FROM job_postings 
                    WHERE position_uri = %s;
                """,
                    ("https://www.usajobs.gov/job/12345",),
                )

                result = cur.fetchone()
                assert result[0] == "Senior Data Engineer"
                assert result[1] == "$90,000"

    def test_database_statistics(self, clean_database, sample_job_postings):
        """Test database statistics functionality."""
        db_manager = clean_database

        # Insert sample data
        db_manager.upsert_jobs(sample_job_postings)

        # Get statistics
        stats = db_manager.get_statistics()

        assert stats["total_jobs"] == 2
        assert stats["unique_organizations"] == 2
        assert isinstance(stats["first_job_date"], datetime)
        assert isinstance(stats["last_job_date"], datetime)

    def test_database_connection_retry(self, clean_database):
        """Test database connection retry mechanism."""
        db_manager = clean_database

        # Test with valid connection
        with db_manager.get_connection() as conn:
            assert conn is not None

        # Test connection context manager cleanup
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                result = cur.fetchone()[0]
                assert result == 1


class TestAPIIntegration:
    """Integration tests for API operations."""

    @patch("requests.Session.get")
    def test_api_client_full_workflow(self, mock_get, api_client, mock_api_response):
        """Test complete API client workflow."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        with patch("time.sleep"):  # Skip actual delays in tests
            # Search for jobs
            result = api_client.search_jobs("data engineering", location="Chicago")

            # Verify API was called correctly
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "Keyword" in call_args[1]["params"]
            assert call_args[1]["params"]["Keyword"] == "data engineering"
            assert call_args[1]["params"]["LocationName"] == "Chicago"

            # Extract job data
            jobs = api_client.extract_job_data(result)

            assert len(jobs) == 2
            assert all(job.validate() for job in jobs)
            assert jobs[0].position_title == "Data Engineer"
            assert jobs[1].position_title == "Senior Data Engineer"

    @patch("requests.Session.get")
    def test_api_client_rate_limiting(self, mock_get, api_client, mock_api_response):
        """Test API client rate limiting."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        with patch("time.sleep") as mock_sleep:
            api_client.search_jobs("data engineering")

            # Verify rate limiting delay was called
            mock_sleep.assert_called_with(1.5)

    @patch("requests.Session.get")
    def test_api_client_error_handling(self, mock_get, api_client):
        """Test API client error handling."""
        # Test HTTP error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server Error")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            api_client.search_jobs("data engineering")

    @patch("requests.Session.get")
    def test_api_pagination_handling(self, mock_get, api_client):
        """Test handling of paginated API responses."""
        # First page response
        page1_response = {
            "SearchResult": {
                "SearchResultCount": 500,
                "SearchResultCountAll": 1000,
                "SearchResultItems": [
                    {
                        "MatchedObjectDescriptor": {
                            "PositionTitle": f"Data Engineer {i}",
                            "PositionURI": f"https://www.usajobs.gov/job/{i}",
                            "PositionLocation": [
                                {"CityName": "DC", "StateCode": "DC", "CountryCode": "US"}
                            ],
                            "PositionRemuneration": [
                                {"MinimumRange": "80000", "RateIntervalCode": "Per Year"}
                            ],
                        }
                    }
                    for i in range(500)  # Full page
                ],
            }
        }

        # Second page response (partial)
        page2_response = {
            "SearchResult": {
                "SearchResultCount": 500,
                "SearchResultCountAll": 1000,
                "SearchResultItems": [
                    {
                        "MatchedObjectDescriptor": {
                            "PositionTitle": f"Data Engineer {i}",
                            "PositionURI": f"https://www.usajobs.gov/job/{i}",
                            "PositionLocation": [
                                {"CityName": "DC", "StateCode": "DC", "CountryCode": "US"}
                            ],
                            "PositionRemuneration": [
                                {"MinimumRange": "80000", "RateIntervalCode": "Per Year"}
                            ],
                        }
                    }
                    for i in range(500, 600)  # Partial page
                ],
            }
        }

        mock_response1 = Mock()
        mock_response1.status_code = 200
        mock_response1.raise_for_status = Mock()
        mock_response1.json.return_value = page1_response

        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.raise_for_status = Mock()
        mock_response2.json.return_value = page2_response

        mock_get.side_effect = [mock_response1, mock_response2]

        with patch("time.sleep"):
            # Test first page
            result1 = api_client.search_jobs("data engineering", page=1)
            jobs1 = api_client.extract_job_data(result1)
            assert len(jobs1) == 500

            # Test second page
            result2 = api_client.search_jobs("data engineering", page=2)
            jobs2 = api_client.extract_job_data(result2)
            assert len(jobs2) == 100


class TestETLServiceIntegration:
    """Integration tests for the complete ETL service."""

    @patch("etl.etl.USAJobsAPIClient.search_jobs")
    def test_etl_service_full_run(
        self, mock_search_jobs, etl_service, mock_api_response, clean_database
    ):
        """Test complete ETL service run."""
        # Setup mock API response
        mock_search_jobs.return_value = mock_api_response

        # Mock the database manager in ETL service
        etl_service.db_manager = clean_database

        # Run ETL process
        results = etl_service.run(max_pages=1)

        # Verify results
        assert isinstance(results, dict)
        assert results["jobs_extracted"] == 2
        assert results["jobs_inserted"] == 2
        assert results["duration_seconds"] > 0
        assert len(results["errors"]) == 0

        # Verify data in database
        stats = clean_database.get_statistics()
        assert stats["total_jobs"] == 2

    @patch("etl.etl.USAJobsAPIClient.search_jobs")
    def test_etl_service_with_pagination(self, mock_search_jobs, etl_service, clean_database):
        """Test ETL service with multiple pages."""
        # Setup responses for two pages with unique URIs
        page1_items = []
        for i in range(500):
            page1_items.append(
                {
                    "MatchedObjectDescriptor": {
                        "PositionTitle": f"Data Engineer {i}",
                        "PositionURI": f"https://www.usajobs.gov/job/{i}",
                        "PositionLocation": [
                            {"CityName": "DC", "StateCode": "DC", "CountryCode": "US"}
                        ],
                        "PositionRemuneration": [
                            {"MinimumRange": "80000", "RateIntervalCode": "Per Year"}
                        ],
                    }
                }
            )

        page1_response = {
            "SearchResult": {
                "SearchResultCount": 500,
                "SearchResultCountAll": 600,
                "SearchResultItems": page1_items,
            }
        }

        page2_items = []
        for i in range(500, 600):  # Continue with unique IDs
            page2_items.append(
                {
                    "MatchedObjectDescriptor": {
                        "PositionTitle": f"Data Engineer {i}",
                        "PositionURI": f"https://www.usajobs.gov/job/{i}",
                        "PositionLocation": [
                            {"CityName": "DC", "StateCode": "DC", "CountryCode": "US"}
                        ],
                        "PositionRemuneration": [
                            {"MinimumRange": "90000", "RateIntervalCode": "Per Year"}
                        ],
                    }
                }
            )

        page2_response = {
            "SearchResult": {
                "SearchResultCount": 100,
                "SearchResultCountAll": 600,
                "SearchResultItems": page2_items,
            }
        }

        mock_search_jobs.side_effect = [page1_response, page2_response]
        etl_service.db_manager = clean_database

        # Run ETL with multiple pages
        results = etl_service.run(max_pages=2)

        # Verify both pages were processed
        assert results["jobs_extracted"] == 600
        assert mock_search_jobs.call_count == 2

    @patch("etl.etl.USAJobsAPIClient.search_jobs")
    def test_etl_service_error_handling(self, mock_search_jobs, etl_service, clean_database):
        """Test ETL service error handling."""
        # Simulate API error
        mock_search_jobs.side_effect = requests.HTTPError("API Error")
        etl_service.db_manager = clean_database

        # ETL should handle the error gracefully and continue
        results = etl_service.run(max_pages=1)

        # Verify error was captured but service continued
        assert len(results["errors"]) > 0
        assert "API Error" in str(results["errors"])
        assert results["jobs_extracted"] == 0  # No jobs due to API error

    @patch("etl.etl.USAJobsAPIClient.search_jobs")
    def test_etl_service_empty_results(self, mock_search_jobs, etl_service, clean_database):
        """Test ETL service with empty API results."""
        empty_response = {
            "SearchResult": {
                "SearchResultCount": 0,
                "SearchResultCountAll": 0,
                "SearchResultItems": [],
            }
        }

        mock_search_jobs.return_value = empty_response
        etl_service.db_manager = clean_database

        # Run ETL with empty results
        results = etl_service.run(max_pages=1)

        # Verify handling of empty results
        assert results["jobs_extracted"] == 0
        assert results["jobs_inserted"] == 0
        assert len(results["errors"]) == 0


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @patch("etl.etl.USAJobsAPIClient.search_jobs")
    def test_complete_etl_workflow(self, mock_search_jobs, clean_database):
        """Test complete ETL workflow from API to database."""
        # Setup realistic mock data
        mock_response = {
            "SearchResult": {
                "SearchResultCount": 3,
                "SearchResultCountAll": 3,
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
                        }
                    },
                    {
                        "MatchedObjectDescriptor": {
                            "PositionTitle": "Lead Data Engineer",
                            "PositionURI": "https://www.usajobs.gov/job/11111",
                            "PositionLocation": [
                                {
                                    "CityName": "San Francisco",
                                    "StateCode": "CA",
                                    "CountryCode": "US",
                                }
                            ],
                            "PositionRemuneration": [
                                {
                                    "MinimumRange": "110000",
                                    "MaximumRange": "160000",
                                    "RateIntervalCode": "Per Year",
                                }
                            ],
                            "OrganizationName": "Department of Energy",
                        }
                    },
                ],
            }
        }

        mock_search_jobs.return_value = mock_response

        # Create ETL service with test database
        etl_service = ETLService()
        etl_service.db_manager = clean_database

        # Run complete ETL process
        results = etl_service.run(keyword="data engineering", max_pages=1)

        # Verify ETL results
        assert results["jobs_extracted"] == 3
        assert results["jobs_inserted"] == 3
        assert results["duration_seconds"] > 0
        assert results["total_jobs_in_db"] == 3

        # Verify data quality in database
        with clean_database.get_connection() as conn:
            with conn.cursor() as cur:
                # Check all jobs were inserted
                cur.execute("SELECT COUNT(*) FROM job_postings;")
                assert cur.fetchone()[0] == 3

                # Check data completeness
                cur.execute(
                    """
                    SELECT position_title, position_location, organization_name, position_remuneration
                    FROM job_postings 
                    ORDER BY position_title;
                """
                )
                jobs = cur.fetchall()

                # Verify first job
                assert jobs[0][0] == "Data Engineer"
                assert jobs[0][1] == "Washington, DC, US"
                assert jobs[0][2] == "Department of Defense"
                assert "$80,000 - $120,000" in jobs[0][3]

                # Verify second job
                assert jobs[1][0] == "Lead Data Engineer"
                assert jobs[1][1] == "San Francisco, CA, US"
                assert jobs[1][2] == "Department of Energy"

                # Verify third job
                assert jobs[2][0] == "Senior Data Engineer"
                assert jobs[2][1] == "Chicago, IL, US"
                assert jobs[2][2] == "Department of Transportation"

                # Check timestamp fields
                cur.execute(
                    """
                    SELECT extracted_at, created_at, updated_at 
                    FROM job_postings 
                    LIMIT 1;
                """
                )
                timestamps = cur.fetchone()
                assert all(timestamp is not None for timestamp in timestamps)
