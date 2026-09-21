# Bootstrap the bucket before migrating local state into this backend. Terraform
# manages the existing bucket after import; never destroy the state container.
terraform {
  backend "gcs" {}
}

variable "terraform_state_bucket_name" {
  description = "Existing bootstrapped private GCS bucket dedicated to Terraform state."
  type        = string
}

variable "terraform_state_retention_days" {
  description = "Days to keep superseded state versions before lifecycle deletion."
  type        = number
  validation {
    condition     = var.terraform_state_retention_days >= 1 && floor(var.terraform_state_retention_days) == var.terraform_state_retention_days
    error_message = "State retention must be an explicit positive integer."
  }
}

resource "google_storage_bucket" "terraform_state" {
  name                        = var.terraform_state_bucket_name
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
  lifecycle_rule {
    condition { days_since_noncurrent_time = var.terraform_state_retention_days }
    action { type = "Delete" }
  }
  lifecycle { prevent_destroy = true }
}
