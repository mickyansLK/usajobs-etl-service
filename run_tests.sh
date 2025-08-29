#!/bin/bash

# Test Runner Script for USAJOBS ETL Service
# This script runs different types of tests with proper setup and teardown

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_color $RED "❌ Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_color $GREEN "✅ Docker is running"
}

# Function to wait for service to be healthy
wait_for_service() {
    local service=$1
    local max_wait=120
    local wait_time=0
    
    print_color $YELLOW "⏳ Waiting for $service to be healthy..."
    
    while [ $wait_time -lt $max_wait ]; do
        if docker-compose ps $service | grep -q "healthy\|Up"; then
            print_color $GREEN "✅ $service is healthy"
            return 0
        fi
        
        sleep 5
        wait_time=$((wait_time + 5))
        print_color $YELLOW "   Still waiting... ($wait_time/$max_wait seconds)"
    done
    
    print_color $RED "❌ $service failed to become healthy within $max_wait seconds"
    return 1
}

# Function to setup test environment
setup_environment() {
    print_color $BLUE "🚀 Setting up test environment..."
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        print_color $YELLOW "⚠️  .env file not found, creating from example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_color $YELLOW "📝 Please update .env with your USAJOBS API key"
        else
            print_color $RED "❌ .env.example not found. Please create .env manually."
            exit 1
        fi
    fi
    
    # Start services
    print_color $BLUE "🐳 Starting Docker services..."
    docker-compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    wait_for_service postgres
    
    # Install Python dependencies if not installed
    if [ ! -d "venv" ]; then
        print_color $BLUE "🐍 Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    print_color $BLUE "📦 Installing Python dependencies..."
    pip install -r requirements.txt
    pip install pytest pytest-cov pytest-mock pytest-asyncio pytest-xdist psutil
    
    print_color $GREEN "✅ Test environment setup complete"
}

# Function to cleanup test environment
cleanup_environment() {
    print_color $BLUE "🧹 Cleaning up test environment..."
    
    # Stop all services
    docker-compose down -v
    
    # Remove test containers if they exist
    docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true
    
    print_color $GREEN "✅ Cleanup complete"
}

# Function to run unit tests
run_unit_tests() {
    print_color $BLUE "🧪 Running unit tests..."
    
    source venv/bin/activate
    
    pytest tests/test_unit.py -v \
        --cov=etl \
        --cov-report=term-missing \
        --cov-report=html:htmlcov/unit \
        --junit-xml=reports/unit-test-results.xml
    
    if [ $? -eq 0 ]; then
        print_color $GREEN "✅ Unit tests passed"
    else
        print_color $RED "❌ Unit tests failed"
        return 1
    fi
}

# Function to run integration tests
run_integration_tests() {
    print_color $BLUE "🔗 Running integration tests..."
    
    source venv/bin/activate
    
    pytest tests/test_integration.py -v \
        --cov=etl \
        --cov-report=term-missing \
        --cov-report=html:htmlcov/integration \
        --junit-xml=reports/integration-test-results.xml
    
    if [ $? -eq 0 ]; then
        print_color $GREEN "✅ Integration tests passed"
    else
        print_color $RED "❌ Integration tests failed"
        return 1
    fi
}

# Function to run performance tests
run_performance_tests() {
    print_color $BLUE "⚡ Running performance tests..."
    
    source venv/bin/activate
    
    pytest tests/test_performance.py -v \
        --junit-xml=reports/performance-test-results.xml \
        -s  # Show print statements for performance metrics
    
    if [ $? -eq 0 ]; then
        print_color $GREEN "✅ Performance tests passed"
    else
        print_color $RED "❌ Performance tests failed"
        return 1
    fi
}

# Function to run all tests
run_all_tests() {
    print_color $BLUE "🎯 Running all tests..."
    
    source venv/bin/activate
    
    # Create reports directory
    mkdir -p reports htmlcov
    
    # Run all tests with coverage
    pytest tests/ -v \
        --cov=etl \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        --cov-report=xml:reports/coverage.xml \
        --junit-xml=reports/all-test-results.xml \
        --durations=10  # Show 10 slowest tests
    
    if [ $? -eq 0 ]; then
        print_color $GREEN "✅ All tests passed"
        print_color $BLUE "📊 Coverage report generated in htmlcov/index.html"
    else
        print_color $RED "❌ Some tests failed"
        return 1
    fi
}

# Function to run smoke tests (quick validation)
run_smoke_tests() {
    print_color $BLUE "💨 Running smoke tests..."
    
    source venv/bin/activate
    
    # Run a subset of quick tests
    pytest tests/test_unit.py::TestJobPosting::test_job_posting_creation \
           tests/test_unit.py::TestCircuitBreaker::test_circuit_breaker_states \
           tests/test_integration.py::TestDatabaseOperations::test_database_connection \
           -v --tb=short
    
    if [ $? -eq 0 ]; then
        print_color $GREEN "✅ Smoke tests passed"
    else
        print_color $RED "❌ Smoke tests failed"
        return 1
    fi
}

# Function to show test reports
show_reports() {
    print_color $BLUE "📊 Test Reports:"
    
    if [ -d "htmlcov" ]; then
        print_color $GREEN "Coverage Report: file://$(pwd)/htmlcov/index.html"
    fi
    
    if [ -d "reports" ]; then
        echo "Test Results:"
        ls -la reports/
    fi
}

# Main script logic
main() {
    local command=${1:-"help"}
    
    case $command in
        "setup")
            check_docker
            setup_environment
            ;;
        "unit")
            setup_environment
            run_unit_tests
            ;;
        "integration")
            setup_environment
            run_integration_tests
            ;;
        "performance")
            setup_environment
            run_performance_tests
            ;;
        "smoke")
            setup_environment
            run_smoke_tests
            ;;
        "all")
            setup_environment
            run_all_tests
            show_reports
            ;;
        "cleanup")
            cleanup_environment
            ;;
        "reports")
            show_reports
            ;;
        "help"|*)
            print_color $BLUE "USAJOBS ETL Test Runner"
            print_color $BLUE "======================="
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  setup       - Set up test environment"
            echo "  unit        - Run unit tests only"
            echo "  integration - Run integration tests only"
            echo "  performance - Run performance tests only"
            echo "  smoke       - Run smoke tests (quick validation)"
            echo "  all         - Run all tests with coverage"
            echo "  cleanup     - Clean up test environment"
            echo "  reports     - Show test reports"
            echo "  help        - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 setup      # Set up environment"
            echo "  $0 unit       # Run unit tests"
            echo "  $0 all        # Run all tests"
            echo "  $0 cleanup    # Clean up"
            ;;
    esac
}

# Trap to ensure cleanup on script exit
trap cleanup_environment EXIT

# Run main function with all arguments
main "$@"
