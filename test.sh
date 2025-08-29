#!/bin/bash

# USAJOBS ETL Testing Script
set -e

echo "=== USAJOBS ETL Testing Script ==="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Determine compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

print_status "Testing USAJOBS ETL Service..."

# Test 1: Check if services are running
print_status "Test 1: Checking if services are running..."
if $COMPOSE_CMD ps | grep -q "usajobs_postgres.*Up" && $COMPOSE_CMD ps | grep -q "usajobs_etl"; then
    print_status "✅ Services are running"
else
    print_error "❌ Services are not running properly"
    exit 1
fi

# Test 2: Check database connectivity
print_status "Test 2: Testing database connectivity..."
if $COMPOSE_CMD exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    print_status "✅ Database is accessible"
else
    print_error "❌ Database is not accessible"
    exit 1
fi

# Test 3: Check if database schema exists
print_status "Test 3: Checking database schema..."
TABLES_COUNT=$($COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
if [ "$TABLES_COUNT" -gt "0" ]; then
    print_status "✅ Database schema created ($TABLES_COUNT tables found)"
else
    print_warning "⚠️ Database schema not found"
fi

# Test 4: Check job_postings table
print_status "Test 4: Checking job_postings table..."
if $COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -c "\d job_postings" > /dev/null 2>&1; then
    print_status "✅ job_postings table exists"
    
    # Get job count
    JOB_COUNT=$($COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -t -c "SELECT COUNT(*) FROM job_postings;" | tr -d ' ')
    print_status "📊 Jobs in database: $JOB_COUNT"
    
    if [ "$JOB_COUNT" -gt "0" ]; then
        print_status "✅ ETL has processed jobs successfully"
        
        # Show sample data
        print_status "📋 Sample job postings:"
        $COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -c "
            SELECT 
                position_title,
                position_location,
                organization_name,
                created_at
            FROM job_postings 
            ORDER BY created_at DESC 
            LIMIT 5;
        "
    else
        print_warning "⚠️ No jobs found in database yet. ETL may still be running."
    fi
else
    print_error "❌ job_postings table does not exist"
    exit 1
fi

# Test 5: Check database views
print_status "Test 5: Testing database views..."
if $COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -c "SELECT * FROM job_statistics;" > /dev/null 2>&1; then
    print_status "✅ Database views are working"
    
    print_status "📈 Job statistics:"
    $COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -c "SELECT * FROM job_statistics;"
else
    print_warning "⚠️ Database views not working properly"
fi

# Test 6: Check recent ETL runs
print_status "Test 6: Checking ETL logs for recent activity..."
if $COMPOSE_CMD logs etl 2>/dev/null | grep -q "ETL process completed successfully"; then
    print_status "✅ ETL has completed successfully at least once"
else
    print_warning "⚠️ No successful ETL completion found in logs"
fi

# Test 7: API connectivity test (if curl is available)
if command -v curl &> /dev/null; then
    print_status "Test 7: Testing USAJOBS API connectivity..."
    
    # Load API key from .env if available
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | grep USAJOBS_API_KEY | xargs)
    fi
    
    if [ -n "$USAJOBS_API_KEY" ] && [ "$USAJOBS_API_KEY" != "your_api_key_here" ]; then
        if curl -s -H "Authorization-Key: $USAJOBS_API_KEY" \
                -H "User-Agent: tasman-assessment-etl-test/1.0" \
                "https://data.usajobs.gov/api/search?Keyword=test&ResultsPerPage=1" | grep -q "SearchResult"; then
            print_status "✅ USAJOBS API is accessible"
        else
            print_warning "⚠️ USAJOBS API test failed"
        fi
    else
        print_warning "⚠️ Cannot test API - USAJOBS_API_KEY not properly configured"
    fi
fi

# Test 8: Container health checks
print_status "Test 8: Checking container health status..."
POSTGRES_HEALTH=$($COMPOSE_CMD ps --format json | grep usajobs_postgres | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
ETL_HEALTH=$($COMPOSE_CMD ps --format json | grep usajobs_etl | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || echo "no-healthcheck")

if [ "$POSTGRES_HEALTH" = "healthy" ]; then
    print_status "✅ PostgreSQL container is healthy"
else
    print_warning "⚠️ PostgreSQL container health: $POSTGRES_HEALTH"
fi

print_status "ℹ️ ETL container health: $ETL_HEALTH"

# Summary
echo ""
echo "=== Test Summary ==="
print_status "All critical tests passed! 🎉"
echo ""
echo "=== Useful Commands ==="
echo "View live logs: $COMPOSE_CMD logs -f"
echo "Check job count: $COMPOSE_CMD exec postgres psql -U postgres -d usajobs -c 'SELECT COUNT(*) FROM job_postings;'"
echo "View recent jobs: $COMPOSE_CMD exec postgres psql -U postgres -d usajobs -c 'SELECT * FROM recent_job_postings LIMIT 10;'"
echo "Stop services: $COMPOSE_CMD down"
echo "Restart ETL: $COMPOSE_CMD restart etl"
echo ""
print_status "Testing completed successfully!"
