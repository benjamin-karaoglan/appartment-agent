# =============================================================================
# Appartment Agent - GCP Infrastructure
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

  # Backend configuration for state storage
  # Uncomment and configure for team usage
  # backend "gcs" {
  #   bucket = "appartment-agent-tfstate"
  #   prefix = "terraform/state"
  # }
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
  ])

  service            = each.key
  disable_on_destroy = false
}

# =============================================================================
# Networking - VPC for Private Services
# =============================================================================

resource "google_compute_network" "vpc" {
  name                    = "appartment-agent-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "appartment-agent-subnet"
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
  account_id   = "appartment-backend"
  display_name = "Appartment Agent Backend Service"
}

# Frontend Service Account
resource "google_service_account" "frontend" {
  account_id   = "appartment-frontend"
  display_name = "Appartment Agent Frontend Service"
}

# Cloud Build Service Account
resource "google_service_account" "cloudbuild" {
  account_id   = "appartment-cloudbuild"
  display_name = "Appartment Agent Cloud Build"
}

# GitHub Actions Deployer Service Account
resource "google_service_account" "deployer" {
  account_id   = "appartment-deployer"
  display_name = "Appartment Agent GitHub Actions Deployer"
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

# Frontend permissions
resource "google_project_iam_member" "frontend_permissions" {
  for_each = toset([
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
# terraform import google_artifact_registry_repository.docker projects/PROJECT_ID/locations/REGION/repositories/appartment-agent
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "appartment-agent"
  description   = "Docker images for Appartment Agent"
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
  name             = "appartment-agent-db"
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
  name     = "appartment_agent"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "user" {
  name     = "appartment"
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
  name           = "appartment-agent-cache"
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

resource "google_storage_bucket" "documents" {
  name     = "${var.project_id}-documents"
  location = var.region

  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
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

  cors {
    origin          = ["*"]
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

# =============================================================================
# Cloud Run - Backend
# =============================================================================

resource "google_cloud_run_v2_service" "backend" {
  name     = "appartment-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.backend.email

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }

    # Cloud SQL connection for Unix socket access
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }

    scaling {
      min_instance_count = var.environment == "production" ? 1 : 0
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/appartment-agent/backend:latest"

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

      env {
        name  = "LOGFIRE_ENABLED"
        value = "true"
      }

      env {
        name = "LOGFIRE_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.logfire_token.secret_id
            version = "latest"
          }
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
  secret      = google_secret_manager_secret.database_url.id
  # Use Unix socket format for Cloud SQL connection (required for Cloud Run)
  secret_data = "postgresql://appartment:${random_password.db_password.result}@/appartment_agent?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"

  depends_on = [google_sql_database_instance.postgres]
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
        image   = "${var.region}-docker.pkg.dev/${var.project_id}/appartment-agent/backend:latest"
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
  name     = "appartment-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.frontend.email

    scaling {
      min_instance_count = var.environment == "production" ? 1 : 0
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/appartment-agent/frontend:latest"

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
        value = google_cloud_run_v2_service.backend.uri
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }
    }
  }

  depends_on = [google_cloud_run_v2_service.backend]
}

# Allow unauthenticated access to frontend
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
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
