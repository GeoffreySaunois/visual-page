variable "gcp_project_id" {
  description = "Existing personal project approved by the owner; never inferred from active gcloud config."
  type        = string
}
variable "gcp_region" {
  description = "Approved Cloud Run and bucket region."
  type        = string
}
variable "firestore_location" {
  description = "Approved immutable Firestore location."
  type        = string
}
variable "archive_bucket_name" {
  description = "Globally unique bucket name for private published objects."
  type        = string
}
variable "container_image" {
  description = "Reviewed hosted backend image pinned by sha256 digest; the local server is not a hosted backend."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "Use a container image pinned to a sha256 digest."
  }
}
variable "max_instances" {
  description = "Explicit upper bound on Cloud Run instance count."
  type        = number
  validation {
    condition     = var.max_instances >= 1 && floor(var.max_instances) == var.max_instances
    error_message = "max_instances must be a positive integer."
  }
}
variable "cloudflare_account_id" {
  description = "Cloudflare account owning the existing Zero Trust organization."
  type        = string
}
variable "owner_emails" {
  description = "Owners allowed through Access during bootstrap; do not broaden until backend report ACLs are enforced."
  type        = set(string)
  validation {
    condition     = length(var.owner_emails) > 0 && alltrue([for email in var.owner_emails : can(regex("^[^@ ]+@[^@ ]+\\.[^@ ]+$", email))])
    error_message = "Supply at least one explicit owner email address."
  }
}

variable "firestore_database_name" {
  description = "Explicit database name; prefer (default) in a new dedicated personal project to retain eligibility for its free quota."
  type        = string
}
variable "firestore_pitr_enabled" {
  description = "Whether to pay for Firestore point-in-time recovery; recommend false for bootstrap pending owner approval."
  type        = bool
}
variable "archive_noncurrent_retention_days" {
  description = "Days to retain noncurrent object versions before deletion; explicitly bounds version-history retention."
  type        = number
  validation {
    condition     = var.archive_noncurrent_retention_days >= 1 && floor(var.archive_noncurrent_retention_days) == var.archive_noncurrent_retention_days
    error_message = "archive_noncurrent_retention_days must be a positive integer."
  }
}
