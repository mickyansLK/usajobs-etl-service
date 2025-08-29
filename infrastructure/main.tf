terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
}

# Data sources for current client and subscription
data "azurerm_client_config" "current" {}
data "azurerm_subscription" "current" {}

# Random suffix for unique resource names
resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  suffix = random_id.suffix.hex
  common_tags = {
    Environment = var.environment
    Project     = "usajobs-etl"
    Owner       = var.owner
    ManagedBy   = "Terraform"
    CreatedDate = formatdate("YYYY-MM-DD", timestamp())
  }
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "rg-usajobs-etl-${var.environment}-${local.suffix}"
  location = var.location
  tags     = local.common_tags
}

# Log Analytics Workspace for monitoring
resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-usajobs-etl-${var.environment}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.common_tags
}

# Application Insights for application monitoring
resource "azurerm_application_insights" "main" {
  name                = "ai-usajobs-etl-${var.environment}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "other"
  tags                = local.common_tags
}

# Key Vault for secrets management
resource "azurerm_key_vault" "main" {
  name                = "kv-usajobs-${var.environment}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Enable soft delete and purge protection
  soft_delete_retention_days = 7
  purge_protection_enabled   = false # Set to true for production

  # Network access
  network_acls {
    default_action = "Allow" # Restrict to "Deny" for production with specific IPs
    bypass         = "AzureServices"
  }

  tags = local.common_tags
}

# Key Vault access policy for current user/service principal
resource "azurerm_key_vault_access_policy" "current_user" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get", "List", "Set", "Delete", "Recover", "Backup", "Restore", "Purge"
  ]
  
  key_permissions = [
    "Get", "List", "Create", "Delete", "Recover", "Backup", "Restore", "Purge"
  ]
}

# Store USAJOBS API key in Key Vault
resource "azurerm_key_vault_secret" "usajobs_api_key" {
  name         = "usajobs-api-key"
  value        = var.usajobs_api_key
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.common_tags

  depends_on = [azurerm_key_vault_access_policy.current_user]
}

# Store database password in Key Vault
resource "azurerm_key_vault_secret" "postgres_password" {
  name         = "postgres-admin-password"
  value        = var.postgres_admin_password
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.common_tags

  depends_on = [azurerm_key_vault_access_policy.current_user]
}

# Container Registry for Docker images
resource "azurerm_container_registry" "main" {
  name                = "acrusajobsetl${var.environment}${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.acr_sku
  admin_enabled       = true

  # Enable vulnerability scanning
  quarantine_policy_enabled = true
  retention_policy {
    days    = var.acr_retention_days
    enabled = true
  }

  trust_policy {
    enabled = false # Enable for production with content trust
  }

  tags = local.common_tags
}

# PostgreSQL Flexible Server
resource "azurerm_postgresql_flexible_server" "main" {
  name                = "psql-usajobs-etl-${var.environment}-${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  administrator_login    = var.postgres_admin_username
  administrator_password = var.postgres_admin_password

  # Server configuration
  sku_name                     = var.postgres_sku
  version                      = "15"
  storage_mb                   = var.postgres_storage_mb
  backup_retention_days        = var.postgres_backup_retention_days
  geo_redundant_backup_enabled = var.postgres_geo_redundant_backup

  # High availability (optional)
  dynamic "high_availability" {
    for_each = var.postgres_ha_enabled ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  # Maintenance window
  maintenance_window {
    day_of_week  = 0  # Sunday
    start_hour   = 2  # 2 AM
    start_minute = 0
  }

  tags = local.common_tags
}

# PostgreSQL Database
resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "usajobs_etl"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# PostgreSQL Firewall Rule for Azure services
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# PostgreSQL Firewall Rule for Container Apps (if needed)
resource "azurerm_postgresql_flexible_server_firewall_rule" "container_apps" {
  count            = var.allow_public_database_access ? 1 : 0
  name             = "AllowContainerApps"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "255.255.255.255"
}

# User Assigned Managed Identity for Container App
resource "azurerm_user_assigned_identity" "container_app" {
  name                = "id-usajobs-etl-${var.environment}-${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.common_tags
}

# Key Vault access policy for Container App Managed Identity
resource "azurerm_key_vault_access_policy" "container_app" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = azurerm_user_assigned_identity.container_app.tenant_id
  object_id    = azurerm_user_assigned_identity.container_app.principal_id

  secret_permissions = ["Get", "List"]
}

# Role assignment for Container Registry
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.container_app.principal_id
}

# Container App Environment
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-usajobs-etl-${var.environment}-${local.suffix}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.common_tags
}

# Container App for ETL Service
resource "azurerm_container_app" "etl" {
  name                         = "ca-usajobs-etl-${var.environment}-${local.suffix}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.common_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_app.id]
  }

  template {
    min_replicas = 0
    max_replicas = var.container_max_replicas

    container {
      name   = "usajobs-etl"
      image  = "${azurerm_container_registry.main.login_server}/usajobs-etl:${var.container_image_tag}"
      cpu    = var.container_cpu
      memory = var.container_memory

      # Environment variables
      env {
        name        = "USAJOBS_API_KEY"
        secret_name = "usajobs-api-key"
      }
      
      env {
        name  = "POSTGRES_HOST"
        value = azurerm_postgresql_flexible_server.main.fqdn
      }
      
      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }
      
      env {
        name  = "POSTGRES_DB"
        value = azurerm_postgresql_flexible_server_database.main.name
      }
      
      env {
        name  = "POSTGRES_USER"
        value = var.postgres_admin_username
      }
      
      env {
        name        = "POSTGRES_PASSWORD"
        secret_name = "postgres-password"
      }
      
      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }

      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }

      # Resource limits
      resources {
        cpu    = var.container_cpu
        memory = var.container_memory
      }
    }
  }

  # Secrets from Key Vault
  secret {
    name  = "usajobs-api-key"
    value = var.usajobs_api_key
  }

  secret {
    name  = "postgres-password"
    value = var.postgres_admin_password
  }

  # Registry configuration
  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }
}

# Logic App for scheduling (Alternative to Container App Jobs)
resource "azurerm_logic_app_workflow" "scheduler" {
  count               = var.enable_logic_app_scheduler ? 1 : 0
  name                = "la-usajobs-etl-scheduler-${var.environment}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags

  workflow_schema    = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
  workflow_version   = "1.0.0.0"
  workflow_parameters = {}

  # Simple workflow that triggers the Container App daily
  workflow_definition = jsonencode({
    "$schema" = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
    contentVersion = "1.0.0.0"
    triggers = {
      Recurrence = {
        type = "Recurrence"
        recurrence = {
          frequency = "Day"
          interval  = 1
          schedule = {
            hours   = [var.schedule_hour]
            minutes = [0]
          }
          timeZone = var.schedule_timezone
        }
      }
    }
    actions = {
      "HTTP-Trigger-Container-App" = {
        type = "Http"
        inputs = {
          method = "POST"
          uri    = "https://management.azure.com/subscriptions/${data.azurerm_subscription.current.subscription_id}/resourceGroups/${azurerm_resource_group.main.name}/providers/Microsoft.App/containerApps/${azurerm_container_app.etl.name}/start?api-version=2022-03-01"
          headers = {
            "Content-Type" = "application/json"
          }
          authentication = {
            type = "ManagedServiceIdentity"
          }
        }
      }
    }
  })
}

# Storage Account for logs and backups (optional)
resource "azurerm_storage_account" "main" {
  count                    = var.create_storage_account ? 1 : 0
  name                     = "stusajobsetl${var.environment}${local.suffix}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = var.storage_replication_type
  min_tls_version         = "TLS1_2"

  blob_properties {
    delete_retention_policy {
      days = var.blob_retention_days
    }
    versioning_enabled = true
  }

  tags = local.common_tags
}

# Storage Container for logs
resource "azurerm_storage_container" "logs" {
  count                 = var.create_storage_account ? 1 : 0
  name                  = "logs"
  storage_account_name  = azurerm_storage_account.main[0].name
  container_access_type = "private"
}

# Storage Container for backups
resource "azurerm_storage_container" "backups" {
  count                 = var.create_storage_account ? 1 : 0
  name                  = "backups"
  storage_account_name  = azurerm_storage_account.main[0].name
  container_access_type = "private"
}
