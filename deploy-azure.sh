#!/bin/bash

# Azure Infrastructure Deployment Script for USAJOBS ETL
# This script deploys the complete Azure infrastructure using Terraform

set -euo pipefail

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
INFRASTRUCTURE_DIR="$SCRIPT_DIR/infrastructure"
TERRAFORM_VARS_FILE="$INFRASTRUCTURE_DIR/terraform.tfvars"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Azure CLI is installed and logged in
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi

    # Check if logged in to Azure
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi

    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi

    # Check Terraform version
    TERRAFORM_VERSION=$(terraform --version | head -n1 | awk '{print $2}' | sed 's/v//')
    REQUIRED_VERSION="1.0.0"
    if ! printf '%s\n%s\n' "$REQUIRED_VERSION" "$TERRAFORM_VERSION" | sort -V -C; then
        log_error "Terraform version $TERRAFORM_VERSION is too old. Minimum required: $REQUIRED_VERSION"
        exit 1
    fi

    # Check if Docker is installed (for building images)
    if ! command -v docker &> /dev/null; then
        log_warning "Docker is not installed. You'll need to build and push container images separately."
    fi

    log_success "Prerequisites check passed"
}

# Initialize Terraform variables file
initialize_terraform_vars() {
    if [[ ! -f "$TERRAFORM_VARS_FILE" ]]; then
        log_info "Creating terraform.tfvars file..."
        cp "$INFRASTRUCTURE_DIR/terraform.tfvars.example" "$TERRAFORM_VARS_FILE"
        
        log_warning "Please edit $TERRAFORM_VARS_FILE with your actual values:"
        log_warning "  - usajobs_api_key: Get from https://developer.usajobs.gov/APIRequest"
        log_warning "  - postgres_admin_password: Set a secure password"
        log_warning "  - environment: dev/staging/prod"
        log_warning "  - location: Your preferred Azure region"
        
        read -p "Press Enter after updating the terraform.tfvars file..." -r
    fi
}

# Validate Terraform variables
validate_terraform_vars() {
    log_info "Validating Terraform variables..."
    
    cd "$INFRASTRUCTURE_DIR"
    
    # Check if required variables are set
    if grep -q "your-usajobs-api-key-here" "$TERRAFORM_VARS_FILE"; then
        log_error "Please set a valid USAJOBS API key in terraform.tfvars"
        exit 1
    fi
    
    if grep -q "YourSecurePassword123!" "$TERRAFORM_VARS_FILE"; then
        log_warning "Using example password. Consider changing it to a more secure one."
    fi
    
    # Validate Terraform configuration
    if ! terraform validate; then
        log_error "Terraform configuration validation failed"
        exit 1
    fi
    
    log_success "Terraform variables validation passed"
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying Azure infrastructure..."
    
    cd "$INFRASTRUCTURE_DIR"
    
    # Initialize Terraform
    log_info "Initializing Terraform..."
    if ! terraform init; then
        log_error "Terraform initialization failed"
        exit 1
    fi
    
    # Plan deployment
    log_info "Planning Terraform deployment..."
    if ! terraform plan -out=tfplan; then
        log_error "Terraform planning failed"
        exit 1
    fi
    
    # Ask for confirmation
    echo
    log_warning "Review the Terraform plan above."
    read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deployment cancelled by user"
        exit 0
    fi
    
    # Apply deployment
    log_info "Applying Terraform deployment..."
    if ! terraform apply tfplan; then
        log_error "Terraform deployment failed"
        exit 1
    fi
    
    # Clean up plan file
    rm -f tfplan
    
    log_success "Infrastructure deployment completed"
}

# Build and push container image
build_and_push_image() {
    if ! command -v docker &> /dev/null; then
        log_warning "Docker not available. Skipping image build and push."
        log_info "To manually build and push:"
        log_info "  1. Build: docker build -t usajobs-etl:latest ."
        log_info "  2. Get ACR details: terraform output container_registry_login_server"
        log_info "  3. Tag: docker tag usajobs-etl:latest <acr-server>/usajobs-etl:latest"
        log_info "  4. Push: az acr login --name <acr-name> && docker push <acr-server>/usajobs-etl:latest"
        return 0
    fi
    
    cd "$INFRASTRUCTURE_DIR"
    
    # Get ACR details from Terraform output
    log_info "Getting Container Registry details..."
    ACR_NAME=$(terraform output -raw container_registry_name)
    ACR_SERVER=$(terraform output -raw container_registry_login_server)
    
    if [[ -z "$ACR_NAME" || -z "$ACR_SERVER" ]]; then
        log_error "Could not get Container Registry details from Terraform output"
        exit 1
    fi
    
    cd "$SCRIPT_DIR"
    
    # Build Docker image
    log_info "Building Docker image..."
    if ! docker build -t usajobs-etl:latest .; then
        log_error "Docker image build failed"
        exit 1
    fi
    
    # Tag image for ACR
    log_info "Tagging image for Azure Container Registry..."
    docker tag usajobs-etl:latest "$ACR_SERVER/usajobs-etl:latest"
    
    # Login to ACR and push
    log_info "Logging in to Azure Container Registry..."
    if ! az acr login --name "$ACR_NAME"; then
        log_error "Failed to login to Azure Container Registry"
        exit 1
    fi
    
    log_info "Pushing image to Azure Container Registry..."
    if ! docker push "$ACR_SERVER/usajobs-etl:latest"; then
        log_error "Failed to push image to Azure Container Registry"
        exit 1
    fi
    
    log_success "Container image built and pushed successfully"
}

# Display deployment information
display_deployment_info() {
    cd "$INFRASTRUCTURE_DIR"
    
    log_success "Deployment completed successfully!"
    echo
    log_info "Deployment Summary:"
    terraform output deployment_info
    
    echo
    log_info "Application Configuration:"
    terraform output application_config
    
    echo
    log_info "Important URLs and Information:"
    echo "  Resource Group: $(terraform output -raw resource_group_name)"
    echo "  PostgreSQL Server: $(terraform output -raw postgres_server_fqdn)"
    echo "  Container Registry: $(terraform output -raw container_registry_login_server)"
    echo "  Container App: $(terraform output -raw container_app_name)"
    echo "  Key Vault: $(terraform output -raw key_vault_name)"
    
    echo
    log_info "Next Steps:"
    log_info "  1. Monitor the Container App in Azure Portal"
    log_info "  2. Check Application Insights for telemetry"
    log_info "  3. View logs in Log Analytics workspace"
    log_info "  4. Verify ETL job execution in the database"
    
    echo
    log_info "Useful Commands:"
    echo "  # View Container App status"
    echo "  az containerapp show --name $(terraform output -raw container_app_name) --resource-group $(terraform output -raw resource_group_name)"
    
    echo "  # View Container App logs"
    echo "  az containerapp logs show --name $(terraform output -raw container_app_name) --resource-group $(terraform output -raw resource_group_name)"
    
    echo "  # Connect to PostgreSQL"
    echo "  az postgres flexible-server connect --name $(terraform output -raw postgres_server_name) --admin-user $(terraform output -raw postgres_admin_username) --database-name $(terraform output -raw postgres_database_name)"
}

# Cleanup function for script interruption
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log_error "Deployment script failed with exit code $exit_code"
        log_info "Check the error messages above for troubleshooting"
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    echo "=========================================="
    echo "USAJOBS ETL - Azure Infrastructure Deployment"
    echo "=========================================="
    echo
    
    # Get current Azure subscription info
    SUBSCRIPTION_INFO=$(az account show --query "{name:name, id:id}" -o table)
    log_info "Current Azure Subscription:"
    echo "$SUBSCRIPTION_INFO"
    echo
    
    # Ask for confirmation to proceed
    read -p "Continue with deployment in this subscription? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deployment cancelled by user"
        exit 0
    fi
    
    # Execute deployment steps
    check_prerequisites
    initialize_terraform_vars
    validate_terraform_vars
    deploy_infrastructure
    
    # Build and push image (optional)
    read -p "Build and push container image? (Y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "Skipping container image build and push"
    else
        build_and_push_image
    fi
    
    display_deployment_info
    
    log_success "All done! 🎉"
}

# Run main function
main "$@"
