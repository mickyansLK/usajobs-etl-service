# USAJOBS ETL Testing Framework

This comprehensive testing framework provides unit, integration, and performance tests for the USAJOBS ETL service using pytest with fixtures and teardowns.

## Test Structure

```
tests/
├── conftest.py              # pytest configuration and fixtures
├── test_unit.py            # Unit tests for individual components
├── test_integration.py     # Integration tests for end-to-end workflows
└── test_performance.py     # Performance and scalability tests
```

## Testing Framework Features

### 🧪 Test Types

1. **Unit Tests** (`test_unit.py`)
   - JobPosting data class validation
   - CircuitBreaker state management
   - API client functionality 
   - Database manager operations
   - Retry decorator behavior
   - Data validation rules

2. **Integration Tests** (`test_integration.py`)
   - End-to-end ETL workflows
   - Database operations with real containers
   - API integration with mocking
   - Service coordination tests
   - Error handling scenarios

3. **Performance Tests** (`test_performance.py`)
   - Database insertion performance
   - API data extraction throughput
   - Memory usage monitoring
   - Concurrent operation handling
   - Query performance validation
   - Circuit breaker overhead

### 🔧 Fixtures and Setup

#### Docker Container Management
- **`test_database_container`**: Spins up PostgreSQL container for testing
- **`docker_client`**: Provides Docker API client
- **`clean_database`**: Fresh database with schema for each test

#### API Mocking
- **`mock_api_response`**: Standard USAJOBS API response fixtures
- **`mock_empty_api_response`**: Empty response handling
- **`api_client`**: Pre-configured API client with mocking

#### Service Components
- **`etl_service`**: Fully configured ETL service instance
- **`database_manager`**: Database operations manager
- **`setup_test_environment`**: Environment variable configuration

### 🚀 Running Tests

#### Test Runner Script
```bash
# Set up test environment
./run_tests.sh setup

# Run different test types
./run_tests.sh unit          # Unit tests only
./run_tests.sh integration   # Integration tests only  
./run_tests.sh performance   # Performance tests only
./run_tests.sh smoke         # Quick validation tests
./run_tests.sh all           # All tests with coverage

# View test reports
./run_tests.sh reports

# Clean up environment
./run_tests.sh cleanup
```

#### Direct pytest Commands
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_unit.py -v
pytest tests/test_integration.py -v  
pytest tests/test_performance.py -v

# Run with coverage
pytest --cov=etl --cov-report=html

# Run specific test
pytest tests/test_unit.py::TestJobPosting::test_job_posting_creation -v
```

### 📊 Test Coverage

The testing framework provides comprehensive coverage of:

- **Data Models**: JobPosting validation and serialization
- **API Integration**: USAJOBS API client with error handling
- **Database Operations**: CRUD operations, schema validation
- **Circuit Breaker**: Failure handling and state management
- **ETL Pipeline**: End-to-end data processing workflows
- **Performance**: Throughput, latency, and resource utilization
- **Error Scenarios**: Network failures, invalid data, timeouts

### 🛡️ Test Environment

#### Environment Variables
Tests use isolated environment configuration:
```
USAJOBS_API_KEY=test_api_key
POSTGRES_HOST=localhost  
POSTGRES_PORT=5433
POSTGRES_DB=usajobs_test
POSTGRES_USER=postgres
POSTGRES_PASSWORD=test_password
LOG_LEVEL=DEBUG
```

#### Docker Dependencies
- **PostgreSQL 15**: Database container with test schema
- **Health Checks**: Ensures services are ready before testing
- **Volume Management**: Isolated data for test repeatability

### 🔄 Fixtures and Teardowns

#### Setup Fixtures
```python
@pytest.fixture(scope="session")
def test_database_container():
    # Spins up PostgreSQL container
    # Waits for health check
    # Returns container handle
    
@pytest.fixture  
def clean_database():
    # Creates fresh database schema
    # Yields database manager
    # Cleans up test data
```

#### Teardown Process
- **Automatic Cleanup**: Fixtures handle resource cleanup
- **Database Truncation**: Test data removed after each test
- **Container Management**: Docker containers stopped/removed
- **Environment Restoration**: Original env vars restored

### 📈 Performance Testing

#### Benchmarks
- **Database Insertion**: >50 jobs/second for 1000 records
- **API Extraction**: >100 jobs/second for 500 records  
- **Memory Usage**: <100MB for 5000 job processing
- **Query Performance**: <1 second for indexed queries
- **Circuit Breaker**: <100ms overhead for 100 operations

#### Scalability Tests
- **Concurrent Database**: 10 parallel connections
- **Multi-page ETL**: 2000+ jobs across multiple API pages
- **Resource Monitoring**: CPU and memory utilization tracking

### 🐛 Debugging Tests

#### Verbose Output
```bash
pytest -v -s  # Show print statements and verbose output
```

#### Test Reports
```bash
# Generate HTML coverage report
pytest --cov=etl --cov-report=html
open htmlcov/index.html

# Generate JUnit XML for CI/CD
pytest --junit-xml=reports/test-results.xml
```

#### Log Analysis
- **Test Logs**: Available in `./logs/etl.log`
- **Debug Level**: Set via `LOG_LEVEL=DEBUG` 
- **Error Tracking**: Comprehensive exception logging

### 🔧 Configuration

#### pytest Configuration (`pyproject.toml`)
```toml
[tool.pytest.ini_options]
minversion = "6.0"
testpaths = ["tests"]
markers = [
    "unit: Unit tests",
    "integration: Integration tests", 
    "performance: Performance tests",
]
```

#### Coverage Settings
- **Source**: `etl/` module
- **Exclusions**: Tests, virtual environments, migrations
- **Reports**: Terminal, HTML, XML formats

### 🚨 CI/CD Integration

The testing framework is designed for easy CI/CD integration:

1. **Docker Compose**: Consistent environments across platforms
2. **JUnit Reports**: Standard XML output for CI systems
3. **Coverage Reports**: Multiple formats for analysis
4. **Exit Codes**: Proper failure signaling for pipeline control
5. **Performance Metrics**: Baseline comparisons for regression detection

### 🎯 Test Best Practices

#### Test Organization
- **Clear Naming**: Descriptive test and fixture names
- **Isolation**: Each test runs independently 
- **Deterministic**: Consistent results across runs
- **Fast Unit Tests**: Sub-second execution for rapid feedback

#### Mock Strategy  
- **External APIs**: Mock USAJOBS API responses
- **Preserve Logic**: Test actual business logic
- **Realistic Data**: Use representative test data
- **Error Scenarios**: Test failure conditions

#### Performance Testing
- **Baseline Metrics**: Establish performance expectations
- **Resource Monitoring**: Track CPU, memory, I/O usage
- **Scalability Limits**: Test with realistic data volumes
- **Regression Detection**: Alert on performance degradation

## Getting Started

1. **Setup Environment**
   ```bash
   ./run_tests.sh setup
   ```

2. **Run Quick Validation**
   ```bash
   ./run_tests.sh smoke
   ```

3. **Run Full Test Suite** 
   ```bash
   ./run_tests.sh all
   ```

4. **View Coverage Report**
   ```bash
   ./run_tests.sh reports
   ```

The testing framework ensures the USAJOBS ETL service is robust, performant, and maintainable across development, staging, and production environments.
