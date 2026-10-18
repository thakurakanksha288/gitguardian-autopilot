# GitGuardian Autopilot - Google Cloud Infrastructure
# MIT License
# Provisions: Cloud Run, Cloud SQL, Artifact Registry, Cloud Monitoring

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─── Enable Required APIs ─────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sql-component.googleapis.com",
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ─── Artifact Registry ────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "main" {
  depends_on    = [google_project_service.apis]
  location      = var.region
  repository_id = "gitguardian"
  description   = "Docker images for GitGuardian Autopilot"
  format        = "DOCKER"
}

# ─── Cloud SQL (PostgreSQL) ───────────────────────────────────────────────────
resource "google_sql_database_instance" "main" {
  depends_on       = [google_project_service.apis]
  name             = "gitguardian-db"
  database_version = "POSTGRES_15"
  region           = var.region
  deletion_protection = false

  settings {
    tier              = "db-f1-micro"  # Smallest tier for cost efficiency
    availability_type = "ZONAL"
    disk_size         = 10
    disk_type         = "PD_SSD"

    backup_configuration {
      enabled = true
    }

    ip_configuration {
      ipv4_enabled = false  # Use private IP only
      enable_private_path_for_google_cloud_services = true
    }
  }
}

resource "google_sql_database" "main" {
  name     = "taskmanager"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "app_user" {
  name     = "appuser"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}

# ─── Service Account for Cloud Run ───────────────────────────────────────────
resource "google_service_account" "cloud_run" {
  account_id   = "gitguardian-run-sa"
  display_name = "GitGuardian Cloud Run Service Account"
}

resource "google_project_iam_member" "cloud_run_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# ─── Cloud Run: Task Manager API ─────────────────────────────────────────────
resource "google_cloud_run_v2_service" "task_manager" {
  depends_on = [google_project_service.apis]
  name       = "task-manager"
  location   = var.region
  ingress    = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run.email
    
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/gitguardian/task-manager:latest"
      
      ports {
        container_port = 8080
      }

      env {
        name  = "DATABASE_URL"
        value = "postgresql+psycopg2://appuser:${var.db_password}@/taskmanager?host=/cloudsql/${var.project_id}:${var.region}:gitguardian-db"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }
  }
}

# Allow unauthenticated access to the service
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.task_manager.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ─── Cloud Run: Webhook Receiver ─────────────────────────────────────────────
resource "google_cloud_run_v2_service" "webhook_receiver" {
  depends_on = [google_project_service.apis]
  name       = "webhook-receiver"
  location   = var.region
  ingress    = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/gitguardian/webhook-receiver:latest"
      
      ports {
        container_port = 8081
      }

      env {
        name  = "GITLAB_URL"
        value = "https://gitlab.com"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GITLAB_TOKEN"
        value = var.gitlab_token
      }
      env {
        name  = "GITLAB_PROJECT_ID"
        value = var.gitlab_project_id
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "webhook_public_access" {
  name     = google_cloud_run_v2_service.webhook_receiver.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ─── Outputs ─────────────────────────────────────────────────────────────────
output "task_manager_url" {
  value       = google_cloud_run_v2_service.task_manager.uri
  description = "The URL of the Task Manager Cloud Run service"
}

output "webhook_receiver_url" {
  value       = google_cloud_run_v2_service.webhook_receiver.uri
  description = "The URL of the Webhook Receiver Cloud Run service"
}

output "db_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "Cloud SQL connection name for Cloud Run"
}
