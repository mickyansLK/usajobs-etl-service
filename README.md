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

## Testing

### Manual Testing

```bash
# Test database connection
docker exec -it usajobs_postgres psql -U postgres -d usajobs -c "SELECT COUNT(*) FROM job_postings;"

# View recent jobs
docker exec -it usajobs_postgres psql -U postgres -d usajobs -c "SELECT position_title, position_location FROM job_postings ORDER BY created_at DESC LIMIT 10;"
```

### Production Monitoring

Monitor the following metrics:
- ETL job success/failure rates
- API response times
- Database connection health
- Container resource usage

## License

This project is developed as part of a technical assessment for Tasman Analytics.
