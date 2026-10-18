variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "gitguardian-autopilot"
}

variable "region" {
  description = "Google Cloud region"
  type        = string
  default     = "us-central1"
}

variable "db_password" {
  description = "PostgreSQL database password for the app user"
  type        = string
  sensitive   = true
}

variable "gitlab_token" {
  description = "GitLab Personal Access Token for API access"
  type        = string
  sensitive   = true
}

variable "gitlab_project_id" {
  description = "GitLab project ID (numeric)"
  type        = string
  default     = ""
}
