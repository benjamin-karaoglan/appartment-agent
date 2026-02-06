# =============================================================================
# AppArt Agent - GCP Infrastructure
# =============================================================================
#
# This Terraform configuration deploys:
# - Cloud Run services for Frontend and Backend
# - Cloud SQL PostgreSQL database
# - Memorystore Redis cache
# - Cloud Storage buckets
# - Secret Manager secrets
# - VPC networking with Private Service Access
# - IAM service accounts and permissions
#
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Remote state backend configured in backend.tf
  # See backend.hcl.example for setup instructions
}

# =============================================================================
# Variables
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  default     = "production"
}

variable "domain" {
  description = "Custom domain for the application (optional)"
  type        = string
  default     = ""
}

variable "create_dns_zone" {
  description = "Whether to create/manage a Cloud DNS zone. Set to false if using external DNS (Cloudflare, etc)."
  type        = bool
  default     = true
}

variable "dns_zone_name" {
  description = "Name of the Cloud DNS zone. If purchased via Cloud Domains, check: gcloud dns managed-zones list"
  type        = string
  default     = "" # Auto-generates from domain if empty (e.g., appartagent-com)
}

variable "api_subdomain" {
  description = "Subdomain for the API (backend). e.g., 'api' results in api.yourdomain.com"
  type        = string
  default     = "api"
}

variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro" # Use db-custom-2-4096 for production
}

variable "redis_tier" {
  description = "Memorystore Redis tier"
  type        = string
  default     = "BASIC" # Use STANDARD_HA for production
}

variable "redis_memory_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "logfire_token" {
  description = "Logfire write token for observability (optional). Can also be set via: echo -n 'TOKEN' | gcloud secrets versions add logfire-token --data-file=-"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_oauth_client_id" {
  description = "Google OAuth 2.0 Client ID (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_oauth_client_secret" {
  description = "Google OAuth 2.0 Client Secret (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "min_instances" {
  description = "Minimum instances for Cloud Run services. Set to 1 for always-on (better latency, ~$50/month/service), 0 for scale-to-zero (cold starts, lower cost)"
  type        = number
  default     = 0
}

variable "use_load_balancer" {
  description = "Use Cloud Load Balancer with Certificate Manager instead of Cloud Run domain mappings. Recommended for production - more reliable SSL certificate provisioning."
  type        = bool
  default     = true
}

# =============================================================================
# Provider Configuration
# =============================================================================

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Enable Required APIs
# =============================================================================

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "compute.googleapis.com",
    "aiplatform.googleapis.com",
    "dns.googleapis.com",
    "certificatemanager.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# =============================================================================
# Networking - VPC for Private Services
# =============================================================================

resource "google_compute_network" "vpc" {
  name                    = "appart-agent-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "appart-agent-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id

  private_ip_google_access = true
}

# Private Service Access for Cloud SQL
resource "google_compute_global_address" "private_ip_range" {
  name          = "private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]

  depends_on = [google_project_service.apis]
}

# VPC Connector for Cloud Run (max 25 chars)
resource "google_vpc_access_connector" "connector" {
  name          = "appt-agent-connector"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc.name

  depends_on = [google_project_service.apis]
}

# =============================================================================
# Service Accounts
# =============================================================================

# Backend Service Account
resource "google_service_account" "backend" {
  account_id   = "appart-backend"
  display_name = "AppArt Agent Backend Service"
}

# Frontend Service Account
resource "google_service_account" "frontend" {
  account_id   = "appart-frontend"
  display_name = "AppArt Agent Frontend Service"
}

# Cloud Build Service Account
resource "google_service_account" "cloudbuild" {
  account_id   = "appart-cloudbuild"
  display_name = "AppArt Agent Cloud Build"
}

# GitHub Actions Deployer Service Account
resource "google_service_account" "deployer" {
  account_id   = "appart-deployer"
  display_name = "AppArt Agent GitHub Actions Deployer"
}

# =============================================================================
# IAM Permissions
# =============================================================================

# Backend permissions
resource "google_project_iam_member" "backend_permissions" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
    "roles/aiplatform.user",
    "roles/redis.editor",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# Backend service account needs Token Creator role on itself for GCS signed URL generation
resource "google_service_account_iam_member" "backend_token_creator" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.backend.email}"
}

# Frontend permissions
resource "google_project_iam_member" "frontend_permissions" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.frontend.email}"
}

# Cloud Build permissions
resource "google_project_iam_member" "cloudbuild_permissions" {
  for_each = toset([
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/artifactregistry.writer",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

# GitHub Actions Deployer permissions
resource "google_project_iam_member" "deployer_permissions" {
  for_each = toset([
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/artifactregistry.writer",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
    "roles/storage.admin",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# =============================================================================
# Artifact Registry
# =============================================================================

# Import existing repository if it was created by bootstrap script:
# terraform import google_artifact_registry_repository.docker projects/PROJECT_ID/locations/REGION/repositories/appart-agent
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "appart-agent"
  description   = "Docker images for AppArt Agent"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]

  lifecycle {
    # Prevent errors if repository already exists
    ignore_changes = [description]
  }
}

# =============================================================================
# Cloud SQL PostgreSQL
# =============================================================================

resource "google_sql_database_instance" "postgres" {
  name             = "appart-agent-db"
  database_version = "POSTGRES_15"
  region           = var.region

  depends_on = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier              = var.db_tier
    availability_type = var.environment == "production" ? "REGIONAL" : "ZONAL"
    disk_autoresize   = true
    disk_size         = 20
    disk_type         = "PD_SSD"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = var.environment == "production"
      start_time                     = "03:00"
      location                       = var.region
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }
  }

  deletion_protection = var.environment == "production"
}

resource "google_sql_database" "database" {
  name     = "appart_agent"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "user" {
  name     = "appart"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

# =============================================================================
# Memorystore Redis
# =============================================================================

resource "google_redis_instance" "cache" {
  name           = "appart-agent-cache"
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_size_gb
  region         = var.region

  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  redis_version = "REDIS_7_0"

  depends_on = [
    google_project_service.apis,
    google_service_networking_connection.private_vpc_connection
  ]
}

# =============================================================================
# Cloud Storage Buckets
# =============================================================================

locals {
  google_oauth_enabled = var.google_oauth_client_id != "" && var.google_oauth_client_secret != ""

  # CORS origins - include custom domain if configured
  # Note: We use the known domain patterns rather than referencing the frontend
  # resource to avoid circular dependencies (backend -> buckets -> frontend -> backend)
  cors_origins = var.domain != "" ? [
    "https://${var.domain}",
    "https://www.${var.domain}",
    "http://localhost:3000", # Local development
  ] : ["*"]

  # DNS zone name - use provided name or derive from domain (appartagent.com -> appartagent-com)
  dns_zone_name = var.dns_zone_name != "" ? var.dns_zone_name : replace(var.domain, ".", "-")
}

resource "google_storage_bucket" "documents" {
  name     = "${var.project_id}-documents"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = true # Allow deletion even with objects

  cors {
    origin          = local.cors_origins
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

resource "google_storage_bucket" "photos" {
  name     = "${var.project_id}-photos"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = true # Allow deletion even with objects

  cors {
    origin          = local.cors_origins
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Bucket IAM for backend service account
resource "google_storage_bucket_iam_member" "documents_admin" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_storage_bucket_iam_member" "photos_admin" {
  bucket = google_storage_bucket.photos.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.backend.email}"
}

# =============================================================================
# Secret Manager
# =============================================================================

resource "google_secret_manager_secret" "db_password" {
  secret_id = "db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "jwt-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "jwt_secret" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = random_password.jwt_secret.result
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

# Placeholder secret for Google Cloud API Key (to be set manually)
resource "google_secret_manager_secret" "google_api_key" {
  secret_id = "google-cloud-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# Logfire write token (set value manually or via variable)
# If you created this secret manually in GCP Console, import it:
#   terraform import google_secret_manager_secret.logfire_token projects/PROJECT_ID/secrets/logfire-token
resource "google_secret_manager_secret" "logfire_token" {
  secret_id = "logfire-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# Optional: set initial Logfire token via TF_VAR_logfire_token to avoid manual step
resource "google_secret_manager_secret_version" "logfire_token" {
  count = var.logfire_token != "" ? 1 : 0

  secret      = google_secret_manager_secret.logfire_token.id
  secret_data = var.logfire_token
}

resource "random_password" "better_auth_secret" {
  length  = 64
  special = false
}

# Better Auth Secret
resource "google_secret_manager_secret" "better_auth_secret" {
  secret_id = "better-auth-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "better_auth_secret" {
  secret      = google_secret_manager_secret.better_auth_secret.id
  secret_data = random_password.better_auth_secret.result
}

# Google OAuth Client ID
resource "google_secret_manager_secret" "google_oauth_client_id" {
  secret_id = "google-oauth-client-id"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# Google OAuth Client Secret
resource "google_secret_manager_secret" "google_oauth_client_secret" {
  secret_id = "google-oauth-client-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# Optional: set initial Google OAuth secrets via variables
resource "google_secret_manager_secret_version" "google_oauth_client_id" {
  count = var.google_oauth_client_id != "" ? 1 : 0

  secret      = google_secret_manager_secret.google_oauth_client_id.id
  secret_data = var.google_oauth_client_id
}

resource "google_secret_manager_secret_version" "google_oauth_client_secret" {
  count = var.google_oauth_client_secret != "" ? 1 : 0

  secret      = google_secret_manager_secret.google_oauth_client_secret.id
  secret_data = var.google_oauth_client_secret
}

# Grant frontend service account access to new secrets
resource "google_secret_manager_secret_iam_member" "frontend_better_auth_secret" {
  secret_id = google_secret_manager_secret.better_auth_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.frontend.email}"
}

resource "google_secret_manager_secret_iam_member" "frontend_google_oauth_client_id" {
  count = local.google_oauth_enabled ? 1 : 0

  secret_id = google_secret_manager_secret.google_oauth_client_id.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.frontend.email}"
}

resource "google_secret_manager_secret_iam_member" "frontend_google_oauth_client_secret" {
  count = local.google_oauth_enabled ? 1 : 0

  secret_id = google_secret_manager_secret.google_oauth_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.frontend.email}"
}

resource "google_secret_manager_secret_iam_member" "frontend_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.frontend.email}"
}

# =============================================================================
# Cloud Run - Backend
# =============================================================================

resource "google_cloud_run_v2_service" "backend" {
  name     = "appart-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.backend.email

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"  # Allow external traffic (e.g., Logfire) to bypass VPC
    }

    # Cloud SQL connection for Unix socket access
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }

    scaling {
      # Set to 1 for always-on (better latency, higher cost ~$50/month)
      # Set to 0 for scale-to-zero (cold starts, lower cost)
      min_instance_count = var.min_instances
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/appart-agent/backend:latest"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }

      env {
        name  = "GEMINI_USE_VERTEXAI"
        value = "true"
      }

      env {
        name  = "GEMINI_LLM_MODEL"
        value = "gemini-2.5-flash"
      }

      env {
        name  = "GEMINI_IMAGE_MODEL"
        value = "gemini-2.5-flash-image"
      }

      env {
        name  = "GCS_DOCUMENTS_BUCKET"
        value = google_storage_bucket.documents.name
      }

      env {
        name  = "GCS_PHOTOS_BUCKET"
        value = google_storage_bucket.photos.name
      }

      env {
        name  = "STORAGE_BACKEND"
        value = "gcs"
      }

      env {
        name  = "REDIS_HOST"
        value = google_redis_instance.cache.host
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(google_redis_instance.cache.port)
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = var.logfire_token != "" ? [1] : []
        content {
          name  = "LOGFIRE_ENABLED"
          value = "true"
        }
      }

      dynamic "env" {
        for_each = var.logfire_token != "" ? [1] : []
        content {
          name = "LOGFIRE_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.logfire_token.secret_id
              version = "latest"
            }
          }
        }
      }

      # CORS - Allow custom domain if configured
      dynamic "env" {
        for_each = var.domain != "" ? [1] : []
        content {
          name  = "EXTRA_CORS_ORIGINS"
          value = "https://${var.domain},https://www.${var.domain}"
        }
      }

      # Mount Cloud SQL socket
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        timeout_seconds       = 5
        failure_threshold     = 30
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        period_seconds    = 30
        timeout_seconds   = 5
        failure_threshold = 3
      }
    }

    # Increase startup timeout
    timeout = "300s"
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_version.db_password,
    google_secret_manager_secret_version.jwt_secret,
    google_secret_manager_secret_version.database_url,
    google_sql_database.database,
    google_vpc_access_connector.connector,
    google_redis_instance.cache,
  ]
}

# Database URL secret (constructed from components)
resource "google_secret_manager_secret" "database_url" {
  secret_id = "database-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  # Use Unix socket format for Cloud SQL connection (required for Cloud Run)
  secret_data = "postgresql://appart:${random_password.db_password.result}@/appart_agent?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"

  depends_on = [google_sql_database_instance.postgres]

  # IMPORTANT: Don't recreate if secret already exists with different value
  # The password was set during initial bootstrap and changing it would break connectivity
  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Allow unauthenticated access to backend (API handles its own auth)
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Cloud Run Job - Database Migrations
# =============================================================================
# This job is updated and executed by CI/CD before deploying the API

resource "google_cloud_run_v2_job" "db_migrate" {
  name     = "db-migrate"
  location = var.region

  template {
    template {
      service_account = google_service_account.backend.email
      timeout         = "600s"
      max_retries     = 1

      # VPC access required for private Cloud SQL
      vpc_access {
        connector = google_vpc_access_connector.connector.id
        egress    = "ALL_TRAFFIC"
      }

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.postgres.connection_name]
        }
      }

      containers {
        image   = "${var.region}-docker.pkg.dev/${var.project_id}/appart-agent/backend:latest"
        command = ["/app/.venv/bin/alembic", "upgrade", "head"]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_version.database_url,
    google_sql_database.database,
    google_vpc_access_connector.connector,
  ]
}

# =============================================================================
# Cloud Run - Frontend
# =============================================================================

resource "google_cloud_run_v2_service" "frontend" {
  name     = "appart-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.frontend.email

    # VPC access for Cloud SQL private IP connectivity
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    # Cloud SQL connection for Better Auth database access
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/appart-agent/frontend:latest"

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = var.domain != "" ? "https://${var.api_subdomain}.${var.domain}" : google_cloud_run_v2_service.backend.uri
      }

      # NEXT_PUBLIC_APP_URL: set only when custom domain is configured.
      # Without a domain, auth-client.ts uses window.location.origin (client)
      # and localhost:3000 (server-side, correct inside the container).
      dynamic "env" {
        for_each = var.domain != "" ? [1] : []
        content {
          name  = "NEXT_PUBLIC_APP_URL"
          value = "https://${var.domain}"
        }
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }

      # Better Auth configuration
      dynamic "env" {
        for_each = var.domain != "" ? [1] : []
        content {
          name  = "BETTER_AUTH_URL"
          value = "https://${var.domain}"
        }
      }

      env {
        name = "BETTER_AUTH_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.better_auth_secret.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = local.google_oauth_enabled ? [1] : []
        content {
          name = "GOOGLE_CLIENT_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.google_oauth_client_id.secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = local.google_oauth_enabled ? [1] : []
        content {
          name = "GOOGLE_CLIENT_SECRET"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.google_oauth_client_secret.secret_id
              version = "latest"
            }
          }
        }
      }

      # Mount Cloud SQL socket
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
  }

  depends_on = [
    google_cloud_run_v2_service.backend,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.better_auth_secret,
    google_sql_database.database,
  ]
}

# Allow unauthenticated access to frontend
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Custom Domain Configuration
# =============================================================================
#
# This section configures:
# 1. Cloud DNS managed zone for the domain
# 2. Cloud Run domain mappings for frontend (apex + www) and backend (api subdomain)
# 3. DNS records pointing to Cloud Run
#
# After applying, you need to update your domain registrar's nameservers
# to point to the Google Cloud DNS nameservers (output: dns_nameservers)
#
# =============================================================================

# Cloud DNS Managed Zone
# If you purchased the domain via Cloud Domains, a zone already exists.
# Import it with: terraform import 'google_dns_managed_zone.main[0]' projects/PROJECT_ID/managedZones/ZONE_NAME
# Find zone name: gcloud dns managed-zones list
resource "google_dns_managed_zone" "main" {
  count = var.domain != "" && var.create_dns_zone ? 1 : 0

  name        = local.dns_zone_name
  dns_name    = "${var.domain}."
  description = "DNS zone for ${var.domain}"

  dnssec_config {
    state = "on"
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    # Prevent recreation if zone was created by Cloud Domains
    ignore_changes = [description, dnssec_config]
  }
}

# =============================================================================
# NOTE: If you purchased your domain via Cloud Domains, you need to manually
# configure it to use this Cloud DNS zone's nameservers:
#
#   gcloud domains registrations configure dns YOUR_DOMAIN \
#     --cloud-dns-zone=ZONE_NAME \
#     --project=YOUR_PROJECT_ID
#
# Example:
#   gcloud domains registrations configure dns appartagent.com \
#     --cloud-dns-zone=appartagent-com \
#     --project=benjamin-karaoglan-genai
#
# This only needs to be done once after initial setup.
# =============================================================================

# Cloud Run Domain Mapping - Frontend (apex domain, e.g., appartagent.com)
# Only used when NOT using load balancer
resource "google_cloud_run_domain_mapping" "frontend_apex" {
  count    = var.domain != "" && !var.use_load_balancer ? 1 : 0
  location = var.region
  name     = var.domain

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.frontend.name
  }

  depends_on = [google_cloud_run_v2_service.frontend]
}

# Cloud Run Domain Mapping - Frontend (www subdomain, e.g., www.appartagent.com)
# Only used when NOT using load balancer
resource "google_cloud_run_domain_mapping" "frontend_www" {
  count    = var.domain != "" && !var.use_load_balancer ? 1 : 0
  location = var.region
  name     = "www.${var.domain}"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.frontend.name
  }

  depends_on = [google_cloud_run_v2_service.frontend]
}

# Cloud Run Domain Mapping - Backend API (e.g., api.appartagent.com)
# Only used when NOT using load balancer
resource "google_cloud_run_domain_mapping" "backend_api" {
  count    = var.domain != "" && !var.use_load_balancer ? 1 : 0
  location = var.region
  name     = "${var.api_subdomain}.${var.domain}"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.backend.name
  }

  depends_on = [google_cloud_run_v2_service.backend]
}

# =============================================================================
# DNS Records for Cloud Run Domain Mapping (when NOT using load balancer)
# =============================================================================

# DNS A Records for apex domain (pointing to Cloud Run) - IPv4 only
resource "google_dns_record_set" "frontend_apex" {
  count = var.domain != "" && var.create_dns_zone && !var.use_load_balancer ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = "${var.domain}."
  type         = "A"
  ttl          = 300

  # Filter to only IPv4 addresses (exclude IPv6 which contain ":")
  rrdatas = [
    for ip in google_cloud_run_domain_mapping.frontend_apex[0].status[0].resource_records[*].rrdata :
    ip if !can(regex(":", ip))
  ]

  depends_on = [google_cloud_run_domain_mapping.frontend_apex]
}

# DNS AAAA Records for apex domain (pointing to Cloud Run) - IPv6 only
resource "google_dns_record_set" "frontend_apex_ipv6" {
  count = var.domain != "" && var.create_dns_zone && !var.use_load_balancer ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = "${var.domain}."
  type         = "AAAA"
  ttl          = 300

  # Filter to only IPv6 addresses (contain ":")
  rrdatas = [
    for ip in google_cloud_run_domain_mapping.frontend_apex[0].status[0].resource_records[*].rrdata :
    ip if can(regex(":", ip))
  ]

  depends_on = [google_cloud_run_domain_mapping.frontend_apex]
}

# DNS CNAME Record for www subdomain
resource "google_dns_record_set" "frontend_www" {
  count = var.domain != "" && var.create_dns_zone && !var.use_load_balancer ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = "www.${var.domain}."
  type         = "CNAME"
  ttl          = 300

  rrdatas = ["ghs.googlehosted.com."]

  depends_on = [google_cloud_run_domain_mapping.frontend_www]
}

# DNS CNAME Record for API subdomain (when NOT using load balancer)
resource "google_dns_record_set" "backend_api" {
  count = var.domain != "" && var.create_dns_zone && !var.use_load_balancer ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = "${var.api_subdomain}.${var.domain}."
  type         = "CNAME"
  ttl          = 300

  rrdatas = ["ghs.googlehosted.com."]

  depends_on = [google_cloud_run_domain_mapping.backend_api]
}

# =============================================================================
# Cloud Load Balancer Configuration (when use_load_balancer = true)
# =============================================================================
#
# This provides more reliable SSL certificate provisioning than Cloud Run
# domain mappings. It uses:
# - Global external Application Load Balancer
# - Serverless NEGs pointing to Cloud Run services
# - Certificate Manager for SSL certificates
# - URL map for routing (api.domain -> backend, else -> frontend)
#
# =============================================================================

# Static IP address for the load balancer
resource "google_compute_global_address" "lb_ip" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name         = "appart-agent-lb-ip"
  description  = "Static IP for AppArt Agent load balancer"
  address_type = "EXTERNAL"

  depends_on = [google_project_service.apis]
}

# Serverless NEG for Frontend Cloud Run service
resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name                  = "appart-frontend-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = google_cloud_run_v2_service.frontend.name
  }

  depends_on = [google_cloud_run_v2_service.frontend]
}

# Serverless NEG for Backend Cloud Run service
resource "google_compute_region_network_endpoint_group" "backend_neg" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name                  = "appart-backend-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = google_cloud_run_v2_service.backend.name
  }

  depends_on = [google_cloud_run_v2_service.backend]
}

# Backend service for Frontend
resource "google_compute_backend_service" "frontend" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name                  = "appart-frontend-backend"
  protocol              = "HTTPS"
  port_name             = "http"
  timeout_sec           = 30
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.frontend_neg[0].id
  }

  # Enable Cloud CDN for better performance (optional)
  enable_cdn = false

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# Backend service for Backend API
resource "google_compute_backend_service" "backend" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name                  = "appart-backend-backend"
  protocol              = "HTTPS"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  # Note: timeout_sec is not supported for serverless NEGs

  backend {
    group = google_compute_region_network_endpoint_group.backend_neg[0].id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# URL Map - Routes traffic based on hostname
resource "google_compute_url_map" "main" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name            = "appart-agent-url-map"
  default_service = google_compute_backend_service.frontend[0].id

  # Route api.domain.com to backend
  host_rule {
    hosts        = ["${var.api_subdomain}.${var.domain}"]
    path_matcher = "api"
  }

  path_matcher {
    name            = "api"
    default_service = google_compute_backend_service.backend[0].id
  }

  # Route apex and www to frontend (default)
  host_rule {
    hosts        = [var.domain, "www.${var.domain}"]
    path_matcher = "frontend"
  }

  path_matcher {
    name            = "frontend"
    default_service = google_compute_backend_service.frontend[0].id
  }
}

# URL Map for HTTP to HTTPS redirect
resource "google_compute_url_map" "http_redirect" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name = "appart-agent-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

# Certificate Manager DNS Authorization
resource "google_certificate_manager_dns_authorization" "main" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name        = "appart-agent-dns-auth"
  description = "DNS authorization for ${var.domain}"
  domain      = var.domain

  depends_on = [google_project_service.apis]
}

# Certificate Manager DNS Authorization for www
resource "google_certificate_manager_dns_authorization" "www" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name        = "appart-agent-dns-auth-www"
  description = "DNS authorization for www.${var.domain}"
  domain      = "www.${var.domain}"

  depends_on = [google_project_service.apis]
}

# Certificate Manager DNS Authorization for API
resource "google_certificate_manager_dns_authorization" "api" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name        = "appart-agent-dns-auth-api"
  description = "DNS authorization for ${var.api_subdomain}.${var.domain}"
  domain      = "${var.api_subdomain}.${var.domain}"

  depends_on = [google_project_service.apis]
}

# DNS records for certificate validation
resource "google_dns_record_set" "cert_validation" {
  count = var.domain != "" && var.use_load_balancer && var.create_dns_zone ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = google_certificate_manager_dns_authorization.main[0].dns_resource_record[0].name
  type         = google_certificate_manager_dns_authorization.main[0].dns_resource_record[0].type
  ttl          = 300
  rrdatas      = [google_certificate_manager_dns_authorization.main[0].dns_resource_record[0].data]
}

resource "google_dns_record_set" "cert_validation_www" {
  count = var.domain != "" && var.use_load_balancer && var.create_dns_zone ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = google_certificate_manager_dns_authorization.www[0].dns_resource_record[0].name
  type         = google_certificate_manager_dns_authorization.www[0].dns_resource_record[0].type
  ttl          = 300
  rrdatas      = [google_certificate_manager_dns_authorization.www[0].dns_resource_record[0].data]
}

resource "google_dns_record_set" "cert_validation_api" {
  count = var.domain != "" && var.use_load_balancer && var.create_dns_zone ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = google_certificate_manager_dns_authorization.api[0].dns_resource_record[0].name
  type         = google_certificate_manager_dns_authorization.api[0].dns_resource_record[0].type
  ttl          = 300
  rrdatas      = [google_certificate_manager_dns_authorization.api[0].dns_resource_record[0].data]
}

# Google-managed SSL Certificate via Certificate Manager
resource "google_certificate_manager_certificate" "main" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name        = "appart-agent-cert"
  description = "SSL certificate for ${var.domain}"

  managed {
    domains = [
      var.domain,
      "www.${var.domain}",
      "${var.api_subdomain}.${var.domain}",
    ]
    dns_authorizations = [
      google_certificate_manager_dns_authorization.main[0].id,
      google_certificate_manager_dns_authorization.www[0].id,
      google_certificate_manager_dns_authorization.api[0].id,
    ]
  }

  depends_on = [
    google_dns_record_set.cert_validation,
    google_dns_record_set.cert_validation_www,
    google_dns_record_set.cert_validation_api,
  ]
}

# Certificate Map
resource "google_certificate_manager_certificate_map" "main" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name        = "appart-agent-cert-map"
  description = "Certificate map for ${var.domain}"

  depends_on = [google_project_service.apis]
}

# Certificate Map Entries
resource "google_certificate_manager_certificate_map_entry" "apex" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name         = "appart-agent-cert-entry-apex"
  map          = google_certificate_manager_certificate_map.main[0].name
  certificates = [google_certificate_manager_certificate.main[0].id]
  hostname     = var.domain
}

resource "google_certificate_manager_certificate_map_entry" "www" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name         = "appart-agent-cert-entry-www"
  map          = google_certificate_manager_certificate_map.main[0].name
  certificates = [google_certificate_manager_certificate.main[0].id]
  hostname     = "www.${var.domain}"
}

resource "google_certificate_manager_certificate_map_entry" "api" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name         = "appart-agent-cert-entry-api"
  map          = google_certificate_manager_certificate_map.main[0].name
  certificates = [google_certificate_manager_certificate.main[0].id]
  hostname     = "${var.api_subdomain}.${var.domain}"
}

# Target HTTPS Proxy
resource "google_compute_target_https_proxy" "main" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name             = "appart-agent-https-proxy"
  url_map          = google_compute_url_map.main[0].id
  certificate_map  = "//certificatemanager.googleapis.com/${google_certificate_manager_certificate_map.main[0].id}"

  depends_on = [
    google_certificate_manager_certificate_map_entry.apex,
    google_certificate_manager_certificate_map_entry.www,
    google_certificate_manager_certificate_map_entry.api,
  ]
}

# Target HTTP Proxy (for redirect)
resource "google_compute_target_http_proxy" "redirect" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name    = "appart-agent-http-proxy"
  url_map = google_compute_url_map.http_redirect[0].id
}

# Global Forwarding Rule for HTTPS
resource "google_compute_global_forwarding_rule" "https" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name                  = "appart-agent-https-rule"
  target                = google_compute_target_https_proxy.main[0].id
  port_range            = "443"
  ip_address            = google_compute_global_address.lb_ip[0].address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# Global Forwarding Rule for HTTP (redirect to HTTPS)
resource "google_compute_global_forwarding_rule" "http" {
  count = var.domain != "" && var.use_load_balancer ? 1 : 0

  name                  = "appart-agent-http-rule"
  target                = google_compute_target_http_proxy.redirect[0].id
  port_range            = "80"
  ip_address            = google_compute_global_address.lb_ip[0].address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# =============================================================================
# DNS Records for Load Balancer
# =============================================================================

# DNS A Record for apex domain (pointing to load balancer IP)
resource "google_dns_record_set" "lb_apex" {
  count = var.domain != "" && var.use_load_balancer && var.create_dns_zone ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = "${var.domain}."
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.lb_ip[0].address]
}

# DNS A Record for www subdomain (pointing to load balancer IP)
resource "google_dns_record_set" "lb_www" {
  count = var.domain != "" && var.use_load_balancer && var.create_dns_zone ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = "www.${var.domain}."
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.lb_ip[0].address]
}

# DNS A Record for API subdomain (pointing to load balancer IP)
resource "google_dns_record_set" "lb_api" {
  count = var.domain != "" && var.use_load_balancer && var.create_dns_zone ? 1 : 0

  managed_zone = google_dns_managed_zone.main[0].name
  name         = "${var.api_subdomain}.${var.domain}."
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.lb_ip[0].address]
}

# =============================================================================
# Outputs
# =============================================================================

output "frontend_url" {
  description = "Frontend Cloud Run URL"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "backend_url" {
  description = "Backend Cloud Run URL"
  value       = google_cloud_run_v2_service.backend.uri
}

output "database_instance" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.postgres.name
}

output "redis_host" {
  description = "Redis host"
  value       = google_redis_instance.cache.host
}

output "documents_bucket" {
  description = "Documents GCS bucket"
  value       = google_storage_bucket.documents.name
}

output "photos_bucket" {
  description = "Photos GCS bucket"
  value       = google_storage_bucket.photos.name
}

output "artifact_registry" {
  description = "Artifact Registry repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "backend_service_account" {
  description = "Backend service account email"
  value       = google_service_account.backend.email
}

output "vpc_connector" {
  description = "VPC Connector name"
  value       = google_vpc_access_connector.connector.name
}

output "migration_job" {
  description = "Database migration Cloud Run Job name"
  value       = google_cloud_run_v2_job.db_migrate.name
}

output "deployer_service_account" {
  description = "GitHub Actions deployer service account email"
  value       = google_service_account.deployer.email
}

# =============================================================================
# Custom Domain Outputs
# =============================================================================

output "custom_domain" {
  description = "Custom domain configured for the application"
  value       = var.domain != "" ? var.domain : "Not configured"
}

output "frontend_custom_url" {
  description = "Frontend URL (custom domain or Cloud Run URL)"
  value       = var.domain != "" ? "https://${var.domain}" : google_cloud_run_v2_service.frontend.uri
}

output "backend_custom_url" {
  description = "Backend API URL (custom domain or Cloud Run URL)"
  value       = var.domain != "" ? "https://${var.api_subdomain}.${var.domain}" : google_cloud_run_v2_service.backend.uri
}

output "dns_zone_name" {
  description = "Cloud DNS zone name (for importing existing zones)"
  value       = var.domain != "" && var.create_dns_zone ? local.dns_zone_name : "Not managed by Terraform"
}

output "dns_nameservers" {
  description = "Cloud DNS nameservers (already configured if purchased via Cloud Domains)"
  value       = var.domain != "" && var.create_dns_zone ? google_dns_managed_zone.main[0].name_servers : []
}

output "dns_records_required" {
  description = "DNS records to configure (if not using Cloud DNS)"
  value = var.domain != "" ? {
    apex_domain = {
      type  = "A"
      name  = var.domain
      value = var.use_load_balancer ? "Load balancer IP (see lb_ip output)" : "See domain mapping status for IP addresses"
      note  = var.use_load_balancer ? "Using load balancer" : "Run: gcloud run domain-mappings describe --domain=${var.domain} --region=${var.region}"
    }
    www = {
      type  = "A"
      name  = "www.${var.domain}"
      value = var.use_load_balancer ? "Load balancer IP (see lb_ip output)" : "ghs.googlehosted.com."
    }
    api = {
      type  = "A"
      name  = "${var.api_subdomain}.${var.domain}"
      value = var.use_load_balancer ? "Load balancer IP (see lb_ip output)" : "ghs.googlehosted.com."
    }
  } : null
}

# =============================================================================
# Load Balancer Outputs
# =============================================================================

output "use_load_balancer" {
  description = "Whether using Cloud Load Balancer (true) or Cloud Run domain mappings (false)"
  value       = var.use_load_balancer
}

output "lb_ip" {
  description = "Load balancer static IP address"
  value       = var.domain != "" && var.use_load_balancer ? google_compute_global_address.lb_ip[0].address : "Not using load balancer"
}

output "certificate_status" {
  description = "SSL certificate status check command"
  value       = var.domain != "" && var.use_load_balancer ? "gcloud certificate-manager certificates describe appart-agent-cert --location=global" : "Not using Certificate Manager"
}
