# USAJOBS ETL Service

A production-ready ETL service that extracts job postings from the USAJOBS API for data engineering positions and loads them into a PostgreSQL database.

## 🚀 Features

- **Robust ETL Pipeline**: Extracts data engineering jobs from USAJOBS API
- **Database Integration**: Stores data in PostgreSQL with upsert operations
- **Containerized**: Docker-ready for easy deployment
- **Cloud Infrastructure**: Terraform IaC for Azure deployment
- **Scheduled Execution**: Daily job runs via Azure Logic Apps
- **Production-Ready**: Comprehensive logging, error handling, and rate limiting
- **Circuit Breaker**: API resilience with automatic failure recovery
- **Comprehensive Monitoring**: Detailed metrics and logging

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   USAJOBS API   │───▶│   ETL Service    │───▶│   PostgreSQL    │
│                 │    │   (Container)    │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                               ▼
                       ┌──────────────────┐
                       │ Azure Logic Apps │
                       │   (Scheduler)    │
                       └──────────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose (or Docker with Compose plugin)
- USAJOBS API key ([Get one here](https://developer.usajobs.gov/APIRequest))
- 4GB+ available disk space
- Internet connection for API access

## 🎯 Quick Start

### 1. Clone and Setup

```bash
git clone <repository>
cd tasman
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` file with your credentials:
```bash
# Required: Get your API key from https://developer.usajobs.gov/APIRequest
USAJOBS_API_KEY=your_actual_api_key_here

# Required: Set a secure password
POSTGRES_PASSWORD=YourSecurePassword123!

# Optional: Adjust other settings as needed
LOG_LEVEL=INFO
```

### 3. Deploy with One Command

```bash
./deploy.sh
```

Or manually:
```bash
docker-compose up --build -d
```

### 4. Monitor Progress

```bash
# View logs in real-time
docker-compose logs -f

# Check database content
docker-compose exec postgres psql -U postgres -d usajobs -c "SELECT COUNT(*) FROM job_postings;"

# View recent jobs
docker-compose exec postgres psql -U postgres -d usajobs -c "SELECT * FROM recent_job_postings LIMIT 10;"
```

## Database Schema

```sql
CREATE TABLE job_postings (
    id SERIAL PRIMARY KEY,
    position_title TEXT NOT NULL,
    position_uri TEXT NOT NULL UNIQUE,
    position_location TEXT,
    position_remuneration TEXT,
    extracted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## Cloud Deployment

### Option 1: Automated Azure Deployment (Recommended)

The complete Azure infrastructure is defined using Terraform with a one-click deployment script:

```bash
# Deploy complete infrastructure to Azure
./deploy-azure.sh
```

This deploys:
- **PostgreSQL Flexible Server**: Managed database with backups
- **Container App**: Serverless container hosting with auto-scaling  
- **Container Registry**: Docker image storage
- **Key Vault**: Secure secrets management
- **Logic App**: Daily scheduling
- **Log Analytics + App Insights**: Monitoring and observability

### Option 2: Manual Azure Deployment

```bash
# 1. Configure Terraform
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your API key and settings

# 2. Deploy infrastructure
terraform init
terraform plan
terraform apply

# 3. Build and push container
ACR_NAME=$(terraform output -raw container_registry_name)
ACR_SERVER=$(terraform output -raw container_registry_login_server)

docker build -t usajobs-etl:latest .
docker tag usajobs-etl:latest $ACR_SERVER/usajobs-etl:latest

az acr login --name $ACR_NAME
docker push $ACR_SERVER/usajobs-etl:latest
```

### Option 3: Local Development

For local testing and development:

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USAJOBS_API_KEY` | USAJOBS API key (required) | - |
| `POSTGRES_HOST` | PostgreSQL host | localhost |
| `POSTGRES_PORT` | PostgreSQL port | 5432 |
| `POSTGRES_DB` | Database name | usajobs |
| `POSTGRES_USER` | Database user | postgres |
| `POSTGRES_PASSWORD` | Database password | postgres |

## API Integration

The service searches for jobs with the keyword "data engineering" and extracts:

- **Position Title**: Job title
- **Position URI**: Direct link to job posting
- **Position Location**: Job location(s)
- **Position Remuneration**: Salary information

The API client respects rate limits and includes proper error handling for robust operation.

## Development

### Code Structure

```
├── etl/
│   └── etl.py              # Main ETL service
├── infrastructure/         # Terraform IaC
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── docker-compose.yml      # Local development
├── Dockerfile             # Container definition
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

### Design Decisions

1. **PostgreSQL**: Chosen for ACID compliance and excellent JSON support for future extensions
2. **Container Instances**: Used over Kubernetes for simplicity and cost-effectiveness
3. **Logic Apps**: Chosen for serverless scheduling without managing additional infrastructure
4. **Upsert Operations**: Prevents duplicate job postings while updating existing ones

### Future Enhancements

- **Data Quality Checks**: Add validation rules for extracted data
- **Monitoring**: Implement Azure Application Insights
- **Multi-region Support**: Deploy across multiple Azure regions
- **Historical Analytics**: Add data warehousing capabilities
- **Real-time Processing**: Stream processing for immediate job alerts

## Troubleshooting

### Common Issues

1. **API Rate Limits**: The service includes 1-second delays between requests
2. **Database Connection**: Ensure PostgreSQL is running and accessible
3. **Container Registry**: Verify ACR permissions and login credentials

### Logs

Logs are available in:
- Container output: `docker logs <container_name>`
- Local file: `etl.log`
- Azure: Log Analytics workspace

## 🧪 Testing

This project includes comprehensive testing with 50+ test cases covering unit, integration, and performance scenarios.

### Quick Test Commands

```bash
# Run all tests with coverage
./run_tests.sh all

# Run specific test types
./run_tests.sh unit           # Unit tests only
./run_tests.sh integration    # Integration tests only  
./run_tests.sh performance    # Performance benchmarks
./run_tests.sh smoke          # Quick validation tests

# Set up test environment (first time only)
./run_tests.sh setup
```

### Test Types Available

#### 1. Unit Tests (`tests/test_unit.py`)

Tests individual components in isolation:

```bash
# Run unit tests
./run_tests.sh unit

# Or with pytest directly
pytest tests/test_unit.py -v --cov=etl
```

**What's tested:**

- ✅ JobPosting data validation
- ✅ Circuit breaker functionality
- ✅ API client error handling
- ✅ Database connection management
- ✅ Data parsing and transformation

#### 2. Integration Tests (`tests/test_integration.py`)

Tests component interactions:

```bash
# Run integration tests (requires running database)
docker-compose up -d postgres
./run_tests.sh integration
```

**What's tested:**

- ✅ Database operations (CRUD)
- ✅ API integration with USAJOBS
- ✅ End-to-end ETL pipeline
- ✅ Error recovery scenarios

#### 3. Performance Tests (`tests/test_performance.py`)

Benchmarks and performance validation:

```bash
# Run performance tests
./run_tests.sh performance
```

**What's tested:**

- ✅ ETL processing speed
- ✅ Database query performance
- ✅ Memory usage patterns
- ✅ API response times

#### 4. System Tests (`test.sh`)

Validates running system:

```bash
# Test live system (requires services running)
docker-compose up -d
./test.sh
```

**What's validated:**

- ✅ Service health checks
- ✅ Database connectivity
- ✅ Data integrity
- ✅ API accessibility
- ✅ ETL execution results

### Test Reports and Coverage

```bash
# Generate coverage report
./run_tests.sh all

# View HTML coverage report
open htmlcov/index.html

# View test reports
ls reports/
# - all-test-results.xml
# - coverage.xml
# - unit-test-results.xml
```

### Manual Testing Commands

#### Database Validation

```bash
# Check job count
docker-compose exec postgres psql -U postgres -d usajobs -c "SELECT COUNT(*) FROM job_postings;"

# View recent jobs
docker-compose exec postgres psql -U postgres -d usajobs -c "
SELECT position_title, organization_name, position_location 
FROM job_postings 
ORDER BY created_at DESC 
LIMIT 10;"

# Check data statistics
docker-compose exec postgres psql -U postgres -d usajobs -c "SELECT * FROM job_statistics;"
```

#### API Testing

```bash
# Test API connectivity (requires USAJOBS_API_KEY)
curl -H "Authorization-Key: YOUR_API_KEY" \
     -H "User-Agent: test-client/1.0" \
     "https://data.usajobs.gov/api/search?Keyword=data%20engineering&ResultsPerPage=1"
```

#### ETL Execution Testing

```bash
# Run ETL manually with specific parameters
docker-compose run --rm -e SEARCH_KEYWORD="data scientist" -e SEARCH_LOCATION="Chicago, Illinois" etl

# Monitor ETL logs
docker-compose logs -f etl
```

### Continuous Integration

For CI/CD pipelines, use:

```yaml
# GitHub Actions example
- name: Run Tests
  run: |
    ./run_tests.sh setup
    ./run_tests.sh all
    
- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./reports/coverage.xml
```

### Test Environment Setup

#### First-time Setup

```bash
# Install test dependencies
./run_tests.sh setup

# Or manually
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock pytest-asyncio
```

#### Test Data

Tests use:

- 📁 **Mock data** for unit tests (no external dependencies)
- 🗄️ **Test database** for integration tests (temporary)
- 🌐 **Live API** for system tests (requires API key)

### Troubleshooting Tests

#### Test Issues

```bash
# Database connection issues
docker-compose up -d postgres
docker-compose ps  # Check if postgres is healthy

# Python environment issues
source venv/bin/activate
pip install -r requirements.txt

# Permission issues
chmod +x run_tests.sh test.sh
```

#### Test Configuration

Tests respect these environment variables:

- `USAJOBS_API_KEY` - For API integration tests
- `POSTGRES_HOST` - Database connection (default: localhost)
- `TEST_TIMEOUT` - Test timeout in seconds (default: 30)

### Production Monitoring

Monitor the following metrics:

- ETL job success/failure rates
- API response times
- Database connection health
- Container resource usage

## License

