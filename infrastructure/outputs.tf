# Resource Group
output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Location of the resource group"
  value       = azurerm_resource_group.main.location
}

# PostgreSQL Database
output "postgres_server_name" {
  description = "Name of the PostgreSQL server"
  value       = azurerm_postgresql_flexible_server.main.name
}

output "postgres_server_fqdn" {
  description = "Fully qualified domain name of the PostgreSQL server"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "postgres_database_name" {
  description = "Name of the PostgreSQL database"
  value       = azurerm_postgresql_flexible_server_database.main.name
}

output "postgres_connection_string" {
  description = "PostgreSQL connection string (without password)"
  value = format(
    "postgresql://%s@%s:5432/%s?sslmode=require",
    var.postgres_admin_username,
    azurerm_postgresql_flexible_server.main.fqdn,
    azurerm_postgresql_flexible_server_database.main.name
  )
  sensitive = false
}

# Container Registry
output "container_registry_name" {
  description = "Name of the Azure Container Registry"
  value       = azurerm_container_registry.main.name
}

output "container_registry_login_server" {
  description = "Login server URL for the Azure Container Registry"
  value       = azurerm_container_registry.main.login_server
}

output "container_registry_admin_username" {
  description = "Admin username for the Azure Container Registry"
  value       = azurerm_container_registry.main.admin_username
}

# Container App
output "container_app_name" {
  description = "Name of the Container App"
  value       = azurerm_container_app.etl.name
}

output "container_app_fqdn" {
  description = "Fully qualified domain name of the Container App"
  value       = azurerm_container_app.etl.latest_revision_fqdn
}

output "container_app_environment_name" {
  description = "Name of the Container App Environment"
  value       = azurerm_container_app_environment.main.name
}

# Key Vault
output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = azurerm_key_vault.main.vault_uri
}

# Managed Identity
output "managed_identity_name" {
  description = "Name of the User Assigned Managed Identity"
  value       = azurerm_user_assigned_identity.container_app.name
}

output "managed_identity_client_id" {
  description = "Client ID of the User Assigned Managed Identity"
  value       = azurerm_user_assigned_identity.container_app.client_id
}

output "managed_identity_principal_id" {
  description = "Principal ID of the User Assigned Managed Identity"
  value       = azurerm_user_assigned_identity.container_app.principal_id
}

# Monitoring
output "log_analytics_workspace_name" {
  description = "Name of the Log Analytics Workspace"
  value       = azurerm_log_analytics_workspace.main.name
}

output "log_analytics_workspace_id" {
  description = "ID of the Log Analytics Workspace"
  value       = azurerm_log_analytics_workspace.main.workspace_id
}

output "application_insights_name" {
  description = "Name of the Application Insights instance"
  value       = azurerm_application_insights.main.name
}

output "application_insights_instrumentation_key" {
  description = "Instrumentation key for Application Insights"
  value       = azurerm_application_insights.main.instrumentation_key
  sensitive   = true
}

output "application_insights_connection_string" {
  description = "Connection string for Application Insights"
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

# Logic App Scheduler
output "logic_app_name" {
  description = "Name of the Logic App scheduler"
  value       = var.enable_logic_app_scheduler ? azurerm_logic_app_workflow.scheduler[0].name : null
}

output "logic_app_access_endpoint" {
  description = "Access endpoint for the Logic App"
  value       = var.enable_logic_app_scheduler ? azurerm_logic_app_workflow.scheduler[0].access_endpoint : null
  sensitive   = true
}

# Storage Account (if created)
output "storage_account_name" {
  description = "Name of the storage account"
  value       = var.create_storage_account ? azurerm_storage_account.main[0].name : null
}

output "storage_account_primary_endpoint" {
  description = "Primary blob endpoint of the storage account"
  value       = var.create_storage_account ? azurerm_storage_account.main[0].primary_blob_endpoint : null
}

# Deployment Information
output "deployment_info" {
  description = "Summary of deployed resources"
  value = {
    environment                = var.environment
    location                  = var.location
    resource_group           = azurerm_resource_group.main.name
    postgres_server          = azurerm_postgresql_flexible_server.main.name
    container_registry       = azurerm_container_registry.main.name
    container_app           = azurerm_container_app.etl.name
    key_vault              = azurerm_key_vault.main.name
    log_analytics          = azurerm_log_analytics_workspace.main.name
    application_insights   = azurerm_application_insights.main.name
    managed_identity       = azurerm_user_assigned_identity.container_app.name
    logic_app_scheduler    = var.enable_logic_app_scheduler ? azurerm_logic_app_workflow.scheduler[0].name : "disabled"
    storage_account        = var.create_storage_account ? azurerm_storage_account.main[0].name : "not_created"
  }
}

# Connection Strings and Configuration
output "application_config" {
  description = "Configuration values for the application"
  value = {
    POSTGRES_HOST     = azurerm_postgresql_flexible_server.main.fqdn
    POSTGRES_PORT     = "5432"
    POSTGRES_DB       = azurerm_postgresql_flexible_server_database.main.name
    POSTGRES_USER     = var.postgres_admin_username
    LOG_LEVEL         = var.log_level
    KEY_VAULT_URI     = azurerm_key_vault.main.vault_uri
    ACR_LOGIN_SERVER  = azurerm_container_registry.main.login_server
  }
  sensitive = false
}

# Resource IDs (useful for other Terraform configurations)
output "resource_ids" {
  description = "Azure resource IDs for reference"
  value = {
    resource_group_id           = azurerm_resource_group.main.id
    postgres_server_id          = azurerm_postgresql_flexible_server.main.id
    container_registry_id       = azurerm_container_registry.main.id
    container_app_id           = azurerm_container_app.etl.id
    container_app_environment_id = azurerm_container_app_environment.main.id
    key_vault_id               = azurerm_key_vault.main.id
    managed_identity_id        = azurerm_user_assigned_identity.container_app.id
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
    application_insights_id    = azurerm_application_insights.main.id
    storage_account_id         = var.create_storage_account ? azurerm_storage_account.main[0].id : null
  }
}

# Security Information
output "security_info" {
  description = "Security-related information"
  value = {
    key_vault_name           = azurerm_key_vault.main.name
    managed_identity_name    = azurerm_user_assigned_identity.container_app.name
    postgres_ssl_enforcement = "Enabled"
    container_registry_admin = "Enabled"
    firewall_rules_count    = var.allow_public_database_access ? 2 : 1
  }
  sensitive = false
}
