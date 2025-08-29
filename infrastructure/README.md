# USAJOBS ETL - Azure Infrastructure

This directory contains Terraform configuration files to deploy the USAJOBS ETL service on Azure.

## Architecture

The infrastructure deploys the following Azure resources:

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Azure Logic App   │───▶│   Container App      │───▶│  PostgreSQL Flex    │
│    (Scheduler)      │    │   (ETL Service)      │    │    Server           │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
                                       │
                                       ▼
                           ┌──────────────────────┐
                           │ Container Registry   │
                           │  + Key Vault        │
                           │  + Log Analytics    │
                           │  + App Insights     │
                           │  + Storage Account  │
                           └──────────────────────┘
```

## Resources Deployed

### Core Infrastructure
- **Resource Group**: Contains all related resources
- **Container App Environment**: Serverless compute platform
- **Container App**: Runs the ETL service with auto-scaling
- **PostgreSQL Flexible Server**: Managed database service
- **Container Registry**: Stores Docker images

### Security & Identity
- **User Assigned Managed Identity**: Secure service authentication
- **Key Vault**: Stores secrets (API keys, passwords)
- **Firewall Rules**: Database access control

### Monitoring & Observability
- **Log Analytics Workspace**: Centralized logging
- **Application Insights**: Application performance monitoring

### Scheduling & Storage
- **Logic App**: Daily ETL job scheduling
- **Storage Account**: Logs and backup storage (optional)

## Prerequisites

1. **Azure CLI** installed and logged in:
   ```bash
   az login
   az account set --subscription "your-subscription-id"
   ```

2. **Terraform** installed (version >= 1.0):
   ```bash
   # Install via package manager or download from terraform.io
   terraform --version
   ```

3. **USAJOBS API Key**:
   - Get one at: https://developer.usajobs.gov/APIRequest
   - Keep it secure for the deployment

## Quick Start

### 1. Configure Variables

Copy the example variables file and customize:
```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:
```hcl
# Required variables
usajobs_api_key         = "your-actual-api-key"
postgres_admin_password = "YourSecurePassword123!"

# Optional customizations
environment = "dev"
location   = "East US"
```

### 2. Initialize and Deploy

```bash
# Initialize Terraform
terraform init

# Plan the deployment (review what will be created)
terraform plan

# Deploy the infrastructure
terraform apply
```

### 3. Deploy Container Image

After infrastructure is deployed, build and push your container:

```bash
# Get ACR details from Terraform output
ACR_NAME=$(terraform output -raw container_registry_name)
ACR_SERVER=$(terraform output -raw container_registry_login_server)

# Build and tag the Docker image
docker build -t usajobs-etl:latest .
docker tag usajobs-etl:latest $ACR_SERVER/usajobs-etl:latest

# Login to ACR and push
az acr login --name $ACR_NAME
docker push $ACR_SERVER/usajobs-etl:latest
```

### 4. Verify Deployment

```bash
# Check if all resources are healthy
terraform output deployment_info

# View application configuration
terraform output application_config

# Monitor the Container App
az containerapp show \
  --name $(terraform output -raw container_app_name) \
  --resource-group $(terraform output -raw resource_group_name)
```

## Configuration

### Environment Variables

The following variables can be customized in `terraform.tfvars`:

#### Required Variables
- `usajobs_api_key`: Your USAJOBS API key
- `postgres_admin_password`: Secure password for database

#### Infrastructure Sizing
```hcl
# Database configuration
postgres_sku                  = "B_Standard_B1ms"  # Basic, GP, or Memory Optimized
postgres_storage_mb           = 32768              # Storage in MB
postgres_backup_retention_days = 7                # Backup retention

# Container configuration
container_cpu    = 0.25      # CPU cores
container_memory = "0.5Gi"   # Memory allocation
```

#### Scheduling
```hcl
schedule_hour             = 6      # Hour to run (0-23)
schedule_timezone         = "UTC"  # Timezone
enable_logic_app_scheduler = true  # Enable/disable scheduling
```

### Cost Optimization

For different environments, adjust these settings:

#### Development (Low Cost)
```hcl
postgres_sku           = "B_Standard_B1ms"
postgres_ha_enabled    = false
acr_sku               = "Basic"
container_max_replicas = 1
```

#### Production (High Availability)
```hcl
postgres_sku                  = "GP_Standard_D2s_v3"
postgres_ha_enabled           = true
postgres_geo_redundant_backup = true
acr_sku                      = "Premium"
container_max_replicas       = 3
```

## Security

### Secrets Management
- API keys and passwords are stored in Azure Key Vault
- Container App uses Managed Identity for secure access
- No secrets are stored in plain text in Terraform state

### Network Security
- PostgreSQL server uses SSL/TLS encryption
- Container Registry uses admin authentication
- Firewall rules control database access

### Best Practices Applied
- Non-root container execution
- Least privilege access policies
- Resource tagging for governance
- Backup and retention policies

## Monitoring

### Application Insights
Monitor your ETL jobs with:
- Performance metrics
- Error tracking
- Custom telemetry
- Dependency tracking

### Log Analytics
Centralized logging includes:
- Container App logs
- Database query logs
- Security audit logs
- Performance metrics

### Alerts (Manual Setup Required)
Configure alerts in Azure Portal for:
- ETL job failures
- Database performance issues
- Container App restart events
- Storage quota warnings

## Maintenance

### Updates
```bash
# Update Terraform configuration
terraform plan
terraform apply

# Update container image
docker build -t usajobs-etl:v2.0 .
docker push $ACR_SERVER/usajobs-etl:v2.0

# Update container app to use new image
az containerapp update \
  --name $(terraform output -raw container_app_name) \
  --resource-group $(terraform output -raw resource_group_name) \
  --image $ACR_SERVER/usajobs-etl:v2.0
```

### Backup and Recovery
- PostgreSQL automated backups (7-35 day retention)
- Container Registry image retention policies
- Infrastructure state stored in Terraform state

### Scaling
```bash
# Manual scaling
az containerapp update \
  --name $(terraform output -raw container_app_name) \
  --resource-group $(terraform output -raw resource_group_name) \
  --max-replicas 5

# Or update terraform.tfvars and reapply
```

## Troubleshooting

### Common Issues

1. **Container App Won't Start**
   ```bash
   # Check logs
   az containerapp logs show \
     --name $(terraform output -raw container_app_name) \
     --resource-group $(terraform output -raw resource_group_name)
   ```

2. **Database Connection Issues**
   ```bash
   # Test database connectivity
   az postgres flexible-server connect \
     --name $(terraform output -raw postgres_server_name) \
     --admin-user $(terraform output -raw postgres_admin_username) \
     --database-name $(terraform output -raw postgres_database_name)
   ```

3. **Secret Access Problems**
   ```bash
   # Verify Key Vault access
   az keyvault secret show \
     --vault-name $(terraform output -raw key_vault_name) \
     --name usajobs-api-key
   ```

### Resource Cleanup
```bash
# Destroy all resources (be careful!)
terraform destroy

# Or delete just the resource group
az group delete --name $(terraform output -raw resource_group_name) --yes
```

## Cost Estimation

### Development Environment (~$50-80/month)
- PostgreSQL Basic tier: ~$25/month
- Container App: ~$15/month
- Container Registry Basic: ~$5/month
- Log Analytics: ~$5/month
- Storage: ~$5/month

### Production Environment (~$150-300/month)
- PostgreSQL General Purpose: ~$80/month
- Container App with scaling: ~$50/month
- Container Registry Premium: ~$20/month
- Log Analytics: ~$15/month
- Storage with geo-replication: ~$15/month

## Support

### Documentation
- [Azure Container Apps Documentation](https://docs.microsoft.com/en-us/azure/container-apps/)
- [PostgreSQL Flexible Server](https://docs.microsoft.com/en-us/azure/postgresql/flexible-server/)
- [Terraform Azure Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)

### Monitoring Resources
- Azure Portal: Monitor resource health and performance
- Application Insights: Application-specific metrics
- Log Analytics: Query logs and set up dashboards

This infrastructure provides a production-ready, scalable, and secure environment for running the USAJOBS ETL service on Azure.
