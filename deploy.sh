#!/bin/bash

# USAJOBS ETL Deployment Script
set -e

echo "=== USAJOBS ETL Deployment Script ==="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
print_status "Checking prerequisites..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_warning "Please edit .env file with your actual credentials before continuing."
        print_warning "Especially set your USAJOBS_API_KEY and POSTGRES_PASSWORD"
        read -p "Press Enter to continue after editing .env file..."
    else
        print_error ".env.example file not found. Cannot create .env file."
        exit 1
    fi
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if API key is set
if [ -z "$USAJOBS_API_KEY" ] || [ "$USAJOBS_API_KEY" = "your_api_key_here" ]; then
    print_error "USAJOBS_API_KEY is not set in .env file"
    print_error "Please get your API key from: https://developer.usajobs.gov/APIRequest"
    exit 1
fi

# Create logs directory
print_status "Creating logs directory..."
mkdir -p logs
chmod 755 logs

# Build and start services
print_status "Building Docker image..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

$COMPOSE_CMD build --no-cache

print_status "Starting services..."
$COMPOSE_CMD up -d

print_status "Waiting for services to be healthy..."
sleep 15

# Check if services are running
if $COMPOSE_CMD ps | grep -q "usajobs_postgres.*Up.*healthy" && $COMPOSE_CMD ps | grep -q "usajobs_etl"; then
    print_status "Services are running successfully!"
    
    echo ""
    echo "=== Service Information ==="
    echo "PostgreSQL: localhost:${POSTGRES_PORT:-5432}"
    echo "Database: ${POSTGRES_DB:-usajobs}"
    echo "Username: ${POSTGRES_USER:-postgres}"
    echo ""
    echo "=== Useful Commands ==="
    echo "View logs: $COMPOSE_CMD logs -f"
    echo "Stop services: $COMPOSE_CMD down"
    echo "Restart ETL: $COMPOSE_CMD restart etl"
    echo "Connect to database: $COMPOSE_CMD exec postgres psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-usajobs}"
    echo ""
    echo "=== Check Job Data ==="
    echo "Total jobs: $COMPOSE_CMD exec postgres psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-usajobs} -c 'SELECT COUNT(*) FROM job_postings;'"
    echo "Recent jobs: $COMPOSE_CMD exec postgres psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-usajobs} -c 'SELECT * FROM recent_job_postings LIMIT 10;'"
    
else
    print_error "Services failed to start properly. Check logs with: $COMPOSE_CMD logs"
    exit 1
fi

echo ""
print_status "Deployment completed successfully!"
