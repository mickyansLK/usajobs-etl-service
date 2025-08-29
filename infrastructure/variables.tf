# General Configuration
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
  validation {
    condition     = can(regex("^(dev|staging|prod)$", var.environment))
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "East US"
}

variable "owner" {
  description = "Owner of the resources (for tagging)"
  type        = string
  default     = "DataEngineering"
}

# USAJOBS API Configuration
variable "usajobs_api_key" {
  description = "USAJOBS API key for data extraction"
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.usajobs_api_key) > 10
    error_message = "USAJOBS API key must be provided and be at least 10 characters long."
  }
}

# PostgreSQL Configuration
variable "postgres_admin_username" {
  description = "Administrator username for PostgreSQL server"
  type        = string
  default     = "postgres"
  validation {
    condition     = length(var.postgres_admin_username) >= 4
    error_message = "PostgreSQL admin username must be at least 4 characters long."
  }
}

variable "postgres_admin_password" {
  description = "Administrator password for PostgreSQL server"
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.postgres_admin_password) >= 12
    error_message = "PostgreSQL admin password must be at least 12 characters long."
  }
}

variable "postgres_sku" {
  description = "SKU for PostgreSQL Flexible Server"
  type        = string
  default     = "B_Standard_B1ms"
  validation {
    condition = can(regex("^(B_Standard_B1ms|B_Standard_B2s|GP_Standard_D2s_v3|GP_Standard_D4s_v3|MO_Standard_E2s_v3)$", var.postgres_sku))
    error_message = "PostgreSQL SKU must be a valid Azure PostgreSQL Flexible Server SKU."
  }
}

variable "postgres_storage_mb" {
  description = "Storage size in MB for PostgreSQL server"
  type        = number
  default     = 32768
  validation {
    condition     = var.postgres_storage_mb >= 20480 && var.postgres_storage_mb <= 16777216
    error_message = "PostgreSQL storage must be between 20GB (20480 MB) and 16TB (16777216 MB)."
  }
}

variable "postgres_backup_retention_days" {
  description = "Backup retention period in days for PostgreSQL"
  type        = number
  default     = 7
  validation {
    condition     = var.postgres_backup_retention_days >= 7 && var.postgres_backup_retention_days <= 35
    error_message = "Backup retention must be between 7 and 35 days."
  }
}

variable "postgres_geo_redundant_backup" {
  description = "Enable geo-redundant backup for PostgreSQL"
  type        = bool
  default     = false
}

variable "postgres_ha_enabled" {
  description = "Enable high availability for PostgreSQL"
  type        = bool
  default     = false
}

variable "allow_public_database_access" {
  description = "Allow public access to PostgreSQL database (not recommended for production)"
  type        = bool
  default     = true
}

# Container Registry Configuration
variable "acr_sku" {
  description = "SKU for Azure Container Registry"
  type        = string
  default     = "Basic"
  validation {
    condition     = can(regex("^(Basic|Standard|Premium)$", var.acr_sku))
    error_message = "ACR SKU must be one of: Basic, Standard, Premium."
  }
}

variable "acr_retention_days" {
  description = "Retention days for container images"
  type        = number
  default     = 30
  validation {
    condition     = var.acr_retention_days >= 1 && var.acr_retention_days <= 365
    error_message = "ACR retention days must be between 1 and 365."
  }
}

# Container App Configuration
variable "container_image_tag" {
  description = "Tag for the container image"
  type        = string
  default     = "latest"
}

variable "container_cpu" {
  description = "CPU allocation for container (in cores)"
  type        = number
  default     = 0.25
  validation {
    condition     = contains([0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0], var.container_cpu)
    error_message = "Container CPU must be one of: 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0."
  }
}

variable "container_memory" {
  description = "Memory allocation for container (in GB)"
  type        = string
  default     = "0.5Gi"
  validation {
    condition     = can(regex("^(0.5|1|1.5|2|2.5|3|3.5|4)Gi$", var.container_memory))
    error_message = "Container memory must be one of: 0.5Gi, 1Gi, 1.5Gi, 2Gi, 2.5Gi, 3Gi, 3.5Gi, 4Gi."
  }
}

variable "container_max_replicas" {
  description = "Maximum number of container replicas"
  type        = number
  default     = 1
  validation {
    condition     = var.container_max_replicas >= 1 && var.container_max_replicas <= 10
    error_message = "Maximum replicas must be between 1 and 10."
  }
}

# Logging and Monitoring Configuration
variable "log_level" {
  description = "Log level for the application"
  type        = string
  default     = "INFO"
  validation {
    condition     = can(regex("^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", var.log_level))
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}

variable "log_retention_days" {
  description = "Log retention period in days"
  type        = number
  default     = 30
  validation {
    condition     = var.log_retention_days >= 7 && var.log_retention_days <= 730
    error_message = "Log retention must be between 7 and 730 days."
  }
}

# Scheduling Configuration
variable "enable_logic_app_scheduler" {
  description = "Enable Logic App for scheduling ETL jobs"
  type        = bool
  default     = true
}

variable "schedule_hour" {
  description = "Hour of day to run ETL job (0-23)"
  type        = number
  default     = 6
  validation {
    condition     = var.schedule_hour >= 0 && var.schedule_hour <= 23
    error_message = "Schedule hour must be between 0 and 23."
  }
}

variable "schedule_timezone" {
  description = "Timezone for scheduling (e.g., 'Eastern Standard Time')"
  type        = string
  default     = "UTC"
}

# Storage Configuration
variable "create_storage_account" {
  description = "Create storage account for logs and backups"
  type        = bool
  default     = true
}

variable "storage_replication_type" {
  description = "Storage account replication type"
  type        = string
  default     = "LRS"
  validation {
    condition     = can(regex("^(LRS|GRS|ZRS|GZRS)$", var.storage_replication_type))
    error_message = "Storage replication type must be one of: LRS, GRS, ZRS, GZRS."
  }
}

variable "blob_retention_days" {
  description = "Blob retention period in days"
  type        = number
  default     = 90
  validation {
    condition     = var.blob_retention_days >= 1 && var.blob_retention_days <= 365
    error_message = "Blob retention days must be between 1 and 365."
  }
}
