#!/bin/bash

# USAJOBS ETL Monitoring Script
# This script provides ongoing monitoring of the ETL service

echo "=== USAJOBS ETL Service Monitoring ==="

# Determine compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

# Function to get job statistics
get_job_stats() {
    echo "📊 Database Statistics:"
    $COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -c "
        SELECT 
            'Total Jobs' as metric, 
            COUNT(*)::text as value 
        FROM job_postings
        UNION ALL
        SELECT 
            'Jobs Today' as metric, 
            COUNT(*)::text as value 
        FROM job_postings 
        WHERE created_at >= CURRENT_DATE
        UNION ALL
        SELECT 
            'Jobs This Week' as metric, 
            COUNT(*)::text as value 
        FROM job_postings 
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        UNION ALL
        SELECT 
            'Unique Organizations' as metric, 
            COUNT(DISTINCT organization_name)::text as value 
        FROM job_postings;
    " 2>/dev/null
}

# Function to show recent jobs
show_recent_jobs() {
    echo ""
    echo "📋 Recent Job Postings (Last 5):"
    $COMPOSE_CMD exec -T postgres psql -U postgres -d usajobs -c "
        SELECT 
            LEFT(position_title, 50) as title,
            LEFT(position_location, 30) as location,
            LEFT(organization_name, 30) as organization,
            created_at::date as date
        FROM job_postings 
        ORDER BY created_at DESC 
        LIMIT 5;
    " 2>/dev/null
}

# Function to check service health
check_health() {
    echo ""
    echo "🔍 Service Health Check:"
    
    # Check if containers are running
    if $COMPOSE_CMD ps | grep -q "usajobs_postgres.*Up" && $COMPOSE_CMD ps | grep -q "usajobs_etl"; then
        echo "✅ Containers are running"
    else
        echo "❌ Some containers are not running"
        return 1
    fi
    
    # Check database connectivity
    if $COMPOSE_CMD exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "✅ Database is accessible"
    else
        echo "❌ Database is not accessible"
        return 1
    fi
    
    # Check for recent ETL activity
    RECENT_LOGS=$($COMPOSE_CMD logs --since=1h etl 2>/dev/null | wc -l)
    if [ "$RECENT_LOGS" -gt 0 ]; then
        echo "✅ ETL service is active (recent log entries: $RECENT_LOGS)"
    else
        echo "⚠️ ETL service may be idle (no recent log entries)"
    fi
}

# Function to show resource usage
show_resources() {
    echo ""
    echo "💻 Resource Usage:"
    if command -v docker &> /dev/null; then
        docker stats usajobs_postgres usajobs_etl --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || echo "Could not get resource statistics"
    fi
}

# Function to show disk usage
show_disk_usage() {
    echo ""
    echo "💾 Disk Usage:"
    echo "Logs directory:"
    du -sh logs/ 2>/dev/null || echo "No logs directory found"
    
    echo "Docker volumes:"
    docker volume ls | grep postgres_data 2>/dev/null || echo "No postgres volumes found"
    
    if command -v docker &> /dev/null; then
        echo "Total Docker space:"
        docker system df 2>/dev/null || echo "Could not get Docker space info"
    fi
}

# Main monitoring loop
if [ "$1" = "--watch" ] || [ "$1" = "-w" ]; then
    echo "Starting continuous monitoring (press Ctrl+C to stop)..."
    while true; do
        clear
        echo "=== USAJOBS ETL Service Monitoring $(date) ==="
        check_health
        get_job_stats
        show_recent_jobs
        show_resources
        echo ""
        echo "Press Ctrl+C to stop monitoring..."
        sleep 30
    done
else
    # Single run
    check_health
    get_job_stats
    show_recent_jobs
    show_resources
    show_disk_usage
    
    echo ""
    echo "=== Available Options ==="
    echo "Watch mode: $0 --watch (or -w)"
    echo "View logs: $COMPOSE_CMD logs -f"
    echo "Run tests: ./test.sh"
    echo "Database shell: $COMPOSE_CMD exec postgres psql -U postgres -d usajobs"
fi
