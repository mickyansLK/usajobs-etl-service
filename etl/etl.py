"""
USAJOBS ETL Service

A production-ready ETL service that extracts job postings from the USAJOBS API
for data engineering positions and loads them into a PostgreSQL database.

Features:
- Robust error handling and API rate limiting
- Configurable via environment variables
- Database connection pooling and upsert operations
- Comprehensive logging
- Extensible design for future enhancements
"""
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime
from functools import wraps
from typing import Any, Dict, List, Optional

import psycopg2
import requests
from psycopg2.extras import RealDictCursor, execute_values


# Configure logging with structured format
class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(log_entry)


# Setup logging
log_dir = os.environ.get("LOG_DIR", "./logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(log_dir, "etl.log"), mode="a"),
    ],
)

logger = logging.getLogger(__name__)


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry decorator with exponential backoff"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay

            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"Attempt {attempts} failed for {func.__name__}: {e}. Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

            return None

        return wrapper

    return decorator


@dataclass
class JobPosting:
    """Enhanced data class representing a job posting"""

    position_title: str
    position_uri: str
    position_location: str
    position_remuneration: str
    position_start_date: Optional[date] = None
    position_end_date: Optional[date] = None
    organization_name: Optional[str] = None
    department_name: Optional[str] = None
    job_category: Optional[str] = None
    job_grade: Optional[str] = None
    extracted_at: datetime = None

    def __post_init__(self):
        if self.extracted_at is None:
            self.extracted_at = datetime.now()

    def validate(self) -> bool:
        """Validate job posting data"""
        if not self.position_title or not self.position_title.strip():
            return False
        if not self.position_uri or not self.position_uri.strip():
            return False
        if not self.position_uri.startswith("http"):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return asdict(self)


class CircuitBreaker:
    """Circuit breaker pattern for API resilience"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"

            raise e


class USAJobsAPIClient:
    """Enhanced client for interacting with the USAJOBS API"""

    def __init__(self, api_key: str, base_url: str = "https://data.usajobs.gov/api/search"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Host": "data.usajobs.gov",
                "User-Agent": "tasman-assessment-etl/2.0",
                "Authorization-Key": api_key,
            }
        )
        self.circuit_breaker = CircuitBreaker()
        self.request_count = 0
        self.api_delay = float(os.getenv("API_DELAY", "1.5"))

    @retry(max_attempts=3, delay=2.0)
    def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        results_per_page: int = 500,
        page: int = 1,
    ) -> Dict:
        """Search for jobs using the USAJOBS API with retry logic"""
        params = {
            "Keyword": keyword,
            "ResultsPerPage": min(results_per_page, 500),  # API limit
            "Page": page,
            "WhoMayApply": "All",  # Include all job types
        }

        if location:
            params["LocationName"] = location

        def make_request():
            self.request_count += 1
            logger.info(
                f"Making API request #{self.request_count} - keyword: {keyword}, page: {page}"
            )

            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            # Enhanced rate limiting
            time.sleep(self.api_delay)  # Use configurable delay

            return response.json()

        try:
            return self.circuit_breaker.call(make_request)
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during API request: {e}")
            raise

    def extract_job_data(self, api_response: Dict) -> List[JobPosting]:
        """Extract and validate job data from API response"""
        jobs = []

        try:
            search_result = api_response.get("SearchResult", {})
            search_result_items = search_result.get("SearchResultItems", [])

            logger.info(f"Processing {len(search_result_items)} job postings")

            for item in search_result_items:
                try:
                    match_job = item.get("MatchedObjectDescriptor", {})

                    # Extract core fields
                    position_title = match_job.get("PositionTitle", "").strip()
                    position_uri = match_job.get("PositionURI", "").strip()

                    # Enhanced location parsing
                    position_location = self._parse_location(match_job.get("PositionLocation", []))

                    # Enhanced remuneration parsing
                    position_remuneration = self._parse_remuneration(
                        match_job.get("PositionRemuneration", [])
                    )

                    # Extract additional fields
                    organization_name = match_job.get("OrganizationName", "").strip()
                    department_name = match_job.get("DepartmentName", "").strip()

                    # Parse dates
                    position_start_date = self._parse_date(match_job.get("PositionStartDate"))
                    position_end_date = self._parse_date(match_job.get("PositionEndDate"))

                    # Job classification
                    job_category = (
                        match_job.get("JobCategory", [{}])[0].get("Name", "")
                        if match_job.get("JobCategory")
                        else ""
                    )
                    job_grade = (
                        match_job.get("JobGrade", [{}])[0].get("Code", "")
                        if match_job.get("JobGrade")
                        else ""
                    )

                    job = JobPosting(
                        position_title=position_title,
                        position_uri=position_uri,
                        position_location=position_location,
                        position_remuneration=position_remuneration,
                        position_start_date=position_start_date,
                        position_end_date=position_end_date,
                        organization_name=organization_name,
                        department_name=department_name,
                        job_category=job_category,
                        job_grade=job_grade,
                    )

                    if job.validate():
                        jobs.append(job)
                    else:
                        logger.warning(f"Invalid job data: {position_title}")

                except Exception as e:
                    logger.warning(f"Error processing job item: {e}")
                    continue

            logger.info(f"Successfully extracted {len(jobs)} valid job postings")
            return jobs

        except Exception as e:
            logger.error(f"Error extracting job data: {e}")
            raise

    def _parse_location(self, location_data: List[Dict]) -> str:
        """Parse location data with fallback handling"""
        if not location_data or not isinstance(location_data, list):
            return "Location not specified"

        try:
            location = location_data[0]
            city = location.get("CityName", "")
            state = location.get("StateCode", "")
            country = location.get("CountryCode", "US")

            parts = [p for p in [city, state, country] if p]
            return ", ".join(parts) if parts else "Location not specified"
        except (IndexError, AttributeError):
            return "Location not specified"

    def _parse_remuneration(self, remuneration_data: List[Dict]) -> str:
        """Parse remuneration data with enhanced formatting"""
        if not remuneration_data or not isinstance(remuneration_data, list):
            return "Not specified"

        try:
            remuneration = remuneration_data[0]
            min_range = remuneration.get("MinimumRange", "")
            max_range = remuneration.get("MaximumRange", "")
            rate_interval = remuneration.get("RateIntervalCode", "")

            if min_range and max_range:
                # Convert to int for formatting
                min_val = int(float(min_range))
                max_val = int(float(max_range))
                return f"${min_val:,} - ${max_val:,} {rate_interval}"
            elif min_range:
                # Convert to int for formatting
                min_val = int(float(min_range))
                return f"${min_val:,}+ {rate_interval}"
            else:
                return "Not specified"
        except (IndexError, AttributeError, ValueError):
            return "Not specified"

    def _parse_date(self, date_string: Optional[str]) -> Optional[date]:
        """Parse date string to date object"""
        if not date_string:
            return None

        try:
            return datetime.fromisoformat(date_string.replace("Z", "+00:00")).date()
        except (ValueError, AttributeError):
            return None


class DatabaseManager:
    """Enhanced database manager with connection pooling and transactions"""

    def __init__(self, host: str, port: str, dbname: str, user: str, password: str):
        self.connection_params = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "connect_timeout": 10,
            "application_name": "usajobs-etl",
        }

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @retry(max_attempts=3, delay=2.0)
    def create_tables(self):
        """Create database schema with enhanced error handling"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Read schema from file if it exists, otherwise use embedded schema
                    schema_file = "/app/init.sql"
                    if os.path.exists(schema_file):
                        with open(schema_file, "r") as f:
                            cur.execute(f.read())
                    else:
                        # Fallback embedded schema
                        cur.execute(self._get_embedded_schema())

                    conn.commit()
                    logger.info("Database schema created/verified successfully")
        except Exception as e:
            logger.error(f"Error creating database schema: {e}")
            raise

    def _get_embedded_schema(self) -> str:
        """Embedded database schema as fallback"""
        return """
        CREATE TABLE IF NOT EXISTS job_postings (
            id SERIAL PRIMARY KEY,
            position_title TEXT NOT NULL,
            position_uri TEXT NOT NULL UNIQUE,
            position_location TEXT,
            position_remuneration TEXT,
            position_start_date DATE,
            position_end_date DATE,
            organization_name TEXT,
            department_name TEXT,
            job_category TEXT,
            job_grade TEXT,
            extracted_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_job_postings_title ON job_postings USING gin(to_tsvector('english', position_title));
        CREATE INDEX IF NOT EXISTS idx_job_postings_location ON job_postings(position_location);
        CREATE INDEX IF NOT EXISTS idx_job_postings_created_at ON job_postings(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_job_postings_organization ON job_postings(organization_name);
        CREATE INDEX IF NOT EXISTS idx_job_postings_uri ON job_postings(position_uri);
        
        -- Create a view for recent job postings
        CREATE OR REPLACE VIEW recent_job_postings AS
        SELECT 
            id,
            position_title,
            position_location,
            position_remuneration,
            organization_name,
            department_name,
            job_category,
            created_at,
            updated_at
        FROM job_postings
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY created_at DESC;
        """

    @retry(max_attempts=3, delay=1.0)
    def upsert_jobs(self, jobs: List[JobPosting]) -> Dict[str, int]:
        """Enhanced upsert with detailed statistics and deduplication"""
        if not jobs:
            logger.info("No jobs to upsert")
            return {"inserted": 0, "updated": 0, "total": 0}

        # Deduplicate jobs by position_uri to avoid ON CONFLICT issues
        seen_uris = set()
        unique_jobs = []
        for job in jobs:
            if job.position_uri not in seen_uris:
                unique_jobs.append(job)
                seen_uris.add(job.position_uri)
            else:
                logger.debug(f"Skipping duplicate job URI: {job.position_uri}")

        if len(unique_jobs) < len(jobs):
            logger.info(f"Deduplicated {len(jobs)} jobs to {len(unique_jobs)} unique jobs")

        jobs = unique_jobs

        upsert_sql = """
        INSERT INTO job_postings (
            position_title, position_uri, position_location, position_remuneration,
            position_start_date, position_end_date, organization_name, department_name,
            job_category, job_grade, extracted_at
        )
        VALUES %s
        ON CONFLICT (position_uri)
        DO UPDATE SET
            position_title = EXCLUDED.position_title,
            position_location = EXCLUDED.position_location,
            position_remuneration = EXCLUDED.position_remuneration,
            position_start_date = EXCLUDED.position_start_date,
            position_end_date = EXCLUDED.position_end_date,
            organization_name = EXCLUDED.organization_name,
            department_name = EXCLUDED.department_name,
            job_category = EXCLUDED.job_category,
            job_grade = EXCLUDED.job_grade,
            extracted_at = EXCLUDED.extracted_at,
            updated_at = CURRENT_TIMESTAMP
        RETURNING (xmax = 0) AS inserted;
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Prepare data
                    job_data = [
                        (
                            job.position_title,
                            job.position_uri,
                            job.position_location,
                            job.position_remuneration,
                            job.position_start_date,
                            job.position_end_date,
                            job.organization_name,
                            job.department_name,
                            job.job_category,
                            job.job_grade,
                            job.extracted_at,
                        )
                        for job in jobs
                    ]

                    execute_values(cur, upsert_sql, job_data, page_size=len(job_data))
                    results = cur.fetchall()

                    inserted = sum(1 for r in results if r[0])
                    updated = len(results) - inserted

                    conn.commit()

                    stats = {"inserted": inserted, "updated": updated, "total": len(results)}
                    logger.info(f"Database operation completed: {stats}")
                    return stats

        except Exception as e:
            logger.error(f"Error upserting jobs: {e}")
            raise

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT 
                            COUNT(*) as total_jobs,
                            COUNT(DISTINCT organization_name) as unique_organizations,
                            COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as jobs_today,
                            COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as jobs_week,
                            MAX(created_at) as last_job_date,
                            MIN(created_at) as first_job_date
                        FROM job_postings;
                    """
                    )
                    return dict(cur.fetchone())
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


class ETLService:
    """Enhanced ETL service with comprehensive monitoring"""

    def __init__(self):
        # Load configuration
        self.api_key = self._get_env_var("USAJOBS_API_KEY")

        # Database configuration
        self.db_config = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": os.getenv("POSTGRES_PORT", "5432"),
            "dbname": os.getenv("POSTGRES_DB", "usajobs"),
            "user": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        }

        # Initialize components
        self.api_client = USAJobsAPIClient(self.api_key)
        self.db_manager = DatabaseManager(**self.db_config)

        # Metrics
        self.metrics: Dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "total_api_calls": 0,
            "total_jobs_extracted": 0,
            "total_jobs_loaded": 0,
            "errors": [],
        }

    def _get_env_var(self, var_name: str) -> str:
        """Get required environment variable"""
        value = os.getenv(var_name)
        if not value:
            raise ValueError(f"Required environment variable {var_name} is not set")
        return value

    def run(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the ETL pipeline with comprehensive monitoring"""
        if keyword is None:
            keyword = os.getenv("SEARCH_KEYWORD", "data engineering")
        if location is None:
            location = os.getenv("SEARCH_LOCATION", None)
        if max_pages is None:
            max_pages = int(os.getenv("MAX_PAGES", "20"))

        self.metrics["start_time"] = datetime.now()
        location_info = f", location: '{location}'" if location else ""
        logger.info(f"Starting ETL process for keyword: '{keyword}'{location_info}, max_pages: {max_pages}")

        try:
            # Initialize database
            self.db_manager.create_tables()

            # Get initial statistics
            initial_stats = self.db_manager.get_statistics()
            logger.info(f"Initial database statistics: {initial_stats}")

            # Extract data from API
            all_jobs = []
            page = 1

            while page <= max_pages:
                try:
                    api_response = self.api_client.search_jobs(keyword, location, page=page)
                    self.metrics["total_api_calls"] += 1

                    # Check for results
                    search_result = api_response.get("SearchResult", {})
                    search_result_items = search_result.get("SearchResultItems", [])

                    if not search_result_items:
                        logger.info(f"No more results found on page {page}")
                        break

                    # Extract job data
                    jobs = self.api_client.extract_job_data(api_response)
                    all_jobs.extend(jobs)
                    self.metrics["total_jobs_extracted"] += len(jobs)

                    logger.info(f"Page {page}: Extracted {len(jobs)} jobs, Total: {len(all_jobs)}")

                    # Check pagination
                    search_result_count = search_result.get("SearchResultCount", 0)
                    search_result_count_all = search_result.get("SearchResultCountAll", 0)

                    if (
                        len(search_result_items) < 500
                        or search_result_count >= search_result_count_all
                    ):
                        break

                    page += 1

                except Exception as e:
                    error_msg = f"Error processing page {page}: {e}"
                    self.metrics["errors"].append(error_msg)
                    logger.error(error_msg)

                    # Continue to next page on non-critical errors
                    if "rate limit" not in str(e).lower():
                        page += 1
                        continue
                    else:
                        break

            # Load data into database
            if all_jobs:
                db_stats = self.db_manager.upsert_jobs(all_jobs)
                self.metrics["total_jobs_loaded"] = db_stats["total"]
            else:
                db_stats = {"inserted": 0, "updated": 0, "total": 0}

            # Get final statistics
            final_stats = self.db_manager.get_statistics()

            self.metrics["end_time"] = datetime.now()
            duration = (self.metrics["end_time"] - self.metrics["start_time"]).total_seconds()

            summary = {
                "duration_seconds": duration,
                "api_calls_made": self.metrics["total_api_calls"],
                "jobs_extracted": self.metrics["total_jobs_extracted"],
                "jobs_inserted": db_stats["inserted"],
                "jobs_updated": db_stats["updated"],
                "total_jobs_in_db": final_stats.get("total_jobs", 0),
                "errors": self.metrics["errors"],
            }

            logger.info(f"ETL process completed successfully: {summary}")
            return summary

        except Exception as e:
            self.metrics["end_time"] = datetime.now()
            error_msg = f"ETL process failed: {e}"
            self.metrics["errors"].append(error_msg)
            logger.error(error_msg)
            raise


def main():
    """Main entry point"""
    try:
        logger.info("=== Starting USAJOBS ETL Service ===")

        etl_service = ETLService()
        results = etl_service.run()

        logger.info("=== ETL Service completed successfully ===")
        logger.info(f"Final results: {results}")

        # Exit with success code
        sys.exit(0)

    except KeyboardInterrupt:
        logger.info("ETL process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"ETL process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
