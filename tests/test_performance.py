"""
Performance tests for the USAJOBS ETL Service

These tests verify performance characteristics and resource usage.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import psutil
import pytest

from etl.etl import ETLService, JobPosting, USAJobsAPIClient


class TestPerformance:
    """Performance tests for ETL operations."""

    def test_database_insertion_performance(self, clean_database):
        """Test database insertion performance with large datasets."""
        import uuid

        db_manager = clean_database

        # Generate large dataset with unique URIs
        job_count = 1000
        test_uuid = str(uuid.uuid4())[:8]  # Use UUID to ensure uniqueness
        jobs = []
        for i in range(job_count):
            job = JobPosting(
                position_title=f"Data Engineer {i}",
                position_uri=f"https://www.usajobs.gov/job/perf-{test_uuid}-{i}",  # Unique URIs
                position_location="Washington, DC, US",
                position_remuneration=f"${80000 + i * 100} Per Year",
                organization_name=f"Department {i % 10}",
            )
            jobs.append(job)

        # Measure insertion time
        start_time = time.time()
        stats = db_manager.upsert_jobs(jobs)
        end_time = time.time()

        duration = end_time - start_time

        # Verify performance requirements
        assert stats["inserted"] == job_count  # All should be new since URIs are unique
        assert duration < 30.0  # Should complete within 30 seconds

        # Calculate throughput
        throughput = job_count / duration
        assert throughput > 50  # At least 50 jobs per second

        print(f"Inserted {job_count} jobs in {duration:.2f} seconds ({throughput:.1f} jobs/sec)")

    def test_api_data_extraction_performance(self, api_client):
        """Test API data extraction performance."""
        # Generate large mock response
        job_items = []
        for i in range(500):  # Maximum page size
            job_items.append(
                {
                    "MatchedObjectDescriptor": {
                        "PositionTitle": f"Data Engineer {i}",
                        "PositionURI": f"https://www.usajobs.gov/job/{i}",
                        "PositionLocation": [
                            {"CityName": "DC", "StateCode": "DC", "CountryCode": "US"}
                        ],
                        "PositionRemuneration": [
                            {"MinimumRange": str(80000 + i * 100), "RateIntervalCode": "Per Year"}
                        ],
                        "OrganizationName": f"Department {i % 10}",
                    }
                }
            )

        large_response = {
            "SearchResult": {
                "SearchResultCount": 500,
                "SearchResultCountAll": 500,
                "SearchResultItems": job_items,
            }
        }

        # Measure extraction time
        start_time = time.time()
        jobs = api_client.extract_job_data(large_response)
        end_time = time.time()

        duration = end_time - start_time

        # Verify performance requirements
        assert len(jobs) == 500
        assert duration < 5.0  # Should complete within 5 seconds

        # Calculate throughput
        throughput = len(jobs) / duration
        assert throughput > 100  # At least 100 jobs per second

        print(f"Extracted {len(jobs)} jobs in {duration:.2f} seconds ({throughput:.1f} jobs/sec)")

    def test_memory_usage_large_dataset(self, clean_database):
        """Test memory usage with large datasets."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Generate large dataset
        job_count = 5000
        jobs = []
        for i in range(job_count):
            job = JobPosting(
                position_title=f"Data Engineer {i}",
                position_uri=f"https://www.usajobs.gov/job/{i}",
                position_location="Washington, DC, US",
                position_remuneration=f"${80000 + i * 100} Per Year",
            )
            jobs.append(job)

        peak_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Process the data
        db_manager = clean_database
        db_manager.upsert_jobs(jobs)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory

        # Verify memory usage is reasonable
        assert memory_increase < 100  # Should not use more than 100MB for 5000 jobs

        print(
            f"Memory usage: Initial: {initial_memory:.1f}MB, Peak: {peak_memory:.1f}MB, "
            f"Increase: {memory_increase:.1f}MB"
        )

    @patch("etl.etl.USAJobsAPIClient.search_jobs")
    def test_concurrent_api_requests_performance(self, mock_search_jobs, api_client):
        """Test performance of concurrent API requests."""
        # Setup mock response
        mock_response = {
            "SearchResult": {
                "SearchResultCount": 100,
                "SearchResultCountAll": 100,
                "SearchResultItems": [
                    {
                        "MatchedObjectDescriptor": {
                            "PositionTitle": "Data Engineer",
                            "PositionURI": f"https://www.usajobs.gov/job/{i}",
                            "PositionLocation": [
                                {"CityName": "DC", "StateCode": "DC", "CountryCode": "US"}
                            ],
                            "PositionRemuneration": [
                                {"MinimumRange": "80000", "RateIntervalCode": "Per Year"}
                            ],
                        }
                    }
                    for i in range(100)
                ],
            }
        }

        mock_search_jobs.return_value = mock_response

        def make_api_call():
            return api_client.search_jobs("data engineering")

        # Test concurrent requests
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_api_call) for _ in range(10)]
            results = [future.result() for future in futures]

        end_time = time.time()
        duration = end_time - start_time

        # Verify all requests completed
        assert len(results) == 10
        assert all(result is not None for result in results)

        # Should complete within reasonable time even with rate limiting
        assert duration < 60.0  # 10 requests with 1.5s delay each should be ~15s + overhead

        print(f"Completed 10 concurrent API requests in {duration:.2f} seconds")


class TestScalability:
    """Tests for system scalability."""

    def test_database_connection_pooling(self, clean_database):
        """Test database performance with multiple concurrent connections."""
        db_manager = clean_database

        def database_operation(job_id):
            job = JobPosting(
                position_title=f"Data Engineer {job_id}",
                position_uri=f"https://www.usajobs.gov/job/{job_id}",
                position_location="Washington, DC",
                position_remuneration="$80,000",
            )
            return db_manager.upsert_jobs([job])

        # Test concurrent database operations
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(database_operation, i) for i in range(50)]
            results = [future.result() for future in futures]

        end_time = time.time()
        duration = end_time - start_time

        # Verify all operations completed successfully
        assert len(results) == 50
        assert all(result["total"] == 1 for result in results)

        # Verify performance
        assert duration < 30.0  # Should complete within 30 seconds

        # Check final database state
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM job_postings;")
                count = cur.fetchone()[0]
                assert count == 50

        print(f"Completed 50 concurrent database operations in {duration:.2f} seconds")

    @patch("etl.etl.USAJobsAPIClient.search_jobs")
    def test_etl_scalability_multiple_pages(self, mock_search_jobs, etl_service, clean_database):
        """Test ETL service scalability with multiple pages."""

        # Setup responses for multiple pages
        def create_page_response(page_num, jobs_per_page=500):
            return {
                "SearchResult": {
                    "SearchResultCount": jobs_per_page,
                    "SearchResultCountAll": 2000,  # Total across all pages
                    "SearchResultItems": [
                        {
                            "MatchedObjectDescriptor": {
                                "PositionTitle": f"Data Engineer Page{page_num} Job{i}",
                                "PositionURI": f"https://www.usajobs.gov/job/{page_num * 1000 + i}",
                                "PositionLocation": [
                                    {"CityName": "DC", "StateCode": "DC", "CountryCode": "US"}
                                ],
                                "PositionRemuneration": [
                                    {"MinimumRange": "80000", "RateIntervalCode": "Per Year"}
                                ],
                            }
                        }
                        for i in range(jobs_per_page)
                    ],
                }
            }

        # Create responses for 4 pages (2000 total jobs)
        page_responses = [
            create_page_response(1, 500),
            create_page_response(2, 500),
            create_page_response(3, 500),
            create_page_response(4, 500),
        ]

        mock_search_jobs.side_effect = page_responses
        etl_service.db_manager = clean_database

        # Measure ETL performance
        start_time = time.time()
        results = etl_service.run(max_pages=4)
        end_time = time.time()

        duration = end_time - start_time

        # Verify results
        assert results["jobs_extracted"] == 2000
        assert results["jobs_inserted"] + results["jobs_updated"] == 2000  # Total processed
        assert mock_search_jobs.call_count == 4

        # Performance requirements
        assert duration < 120.0  # Should complete within 2 minutes

        throughput = results["jobs_extracted"] / duration
        assert throughput > 20  # At least 20 jobs per second end-to-end

        print(
            f"Processed {results['jobs_extracted']} jobs in {duration:.2f} seconds "
            f"({throughput:.1f} jobs/sec)"
        )


class TestResourceUtilization:
    """Tests for resource utilization and limits."""

    def test_cpu_usage_during_etl(self, clean_database):
        """Monitor CPU usage during ETL operations."""
        import os

        import psutil

        process = psutil.Process(os.getpid())

        # Generate test data
        jobs = [
            JobPosting(
                position_title=f"Data Engineer {i}",
                position_uri=f"https://www.usajobs.gov/job/{i}",
                position_location="Washington, DC",
                position_remuneration="$80,000",
            )
            for i in range(1000)
        ]

        # Monitor CPU usage
        cpu_percentages = []

        def monitor_cpu():
            for _ in range(10):
                cpu_percentages.append(process.cpu_percent())
                time.sleep(0.1)

        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_cpu)
        monitor_thread.start()

        # Perform ETL operation
        db_manager = clean_database
        start_time = time.time()
        db_manager.upsert_jobs(jobs)
        end_time = time.time()

        # Wait for monitoring to complete
        monitor_thread.join()

        # Analyze CPU usage
        avg_cpu = sum(cpu_percentages) / len(cpu_percentages) if cpu_percentages else 0
        max_cpu = max(cpu_percentages) if cpu_percentages else 0

        print(f"CPU usage during ETL: Average: {avg_cpu:.1f}%, Peak: {max_cpu:.1f}%")

        # CPU usage should be reasonable
        assert max_cpu < 80.0  # Should not max out CPU

        duration = end_time - start_time
        print(f"ETL operation completed in {duration:.2f} seconds")

    def test_database_query_performance(self, clean_database):
        """Test database query performance with indexed data."""
        db_manager = clean_database

        # Insert test data
        jobs = [
            JobPosting(
                position_title=f"Data Engineer {i}",
                position_uri=f"https://www.usajobs.gov/job/{i}",
                position_location=f"City {i % 10}, State {i % 5}",
                position_remuneration=f"${80000 + i * 100}",
                organization_name=f"Department {i % 20}",
            )
            for i in range(5000)
        ]

        db_manager.upsert_jobs(jobs)

        # Test various query performance
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Test indexed queries
                queries = [
                    "SELECT COUNT(*) FROM job_postings WHERE position_title LIKE 'Data Engineer%';",
                    "SELECT * FROM job_postings WHERE position_location LIKE 'City 1%' LIMIT 100;",
                    "SELECT organization_name, COUNT(*) FROM job_postings GROUP BY organization_name;",
                    "SELECT * FROM job_postings ORDER BY created_at DESC LIMIT 100;",
                    "SELECT * FROM recent_job_postings LIMIT 50;",
                ]

                for query in queries:
                    start_time = time.time()
                    cur.execute(query)
                    results = cur.fetchall()
                    end_time = time.time()

                    duration = end_time - start_time

                    # Each query should complete quickly
                    assert duration < 1.0  # Less than 1 second

                    print(f"Query completed in {duration:.3f}s, returned {len(results)} rows")

    def test_circuit_breaker_performance(self, api_client):
        """Test circuit breaker performance under load."""
        from etl.etl import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=1)

        # Test normal operation performance
        def successful_operation():
            return "success"

        start_time = time.time()
        for _ in range(100):
            result = cb.call(successful_operation)
            assert result == "success"
        end_time = time.time()

        duration = end_time - start_time

        # Circuit breaker should have minimal overhead
        assert duration < 0.1  # Less than 100ms for 100 operations

        print(f"Circuit breaker handled 100 successful operations in {duration:.3f}s")

        # Test failure handling performance
        def failing_operation():
            raise Exception("Test failure")

        failure_count = 0
        start_time = time.time()

        # Trigger failures to open circuit
        for i in range(10):
            try:
                cb.call(failing_operation)
            except Exception:
                failure_count += 1

        end_time = time.time()
        duration = end_time - start_time

        # Should handle failures quickly
        assert duration < 0.1  # Less than 100ms
        assert failure_count >= 5  # Should have failed at least 5 times
        assert cb.state == "OPEN"  # Circuit should be open

        print(f"Circuit breaker handled {failure_count} failures in {duration:.3f}s")
