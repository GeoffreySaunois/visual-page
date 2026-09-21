resource "google_project_service" "api" {
  for_each = toset([
    "run.googleapis.com", "firestore.googleapis.com",
    "storage.googleapis.com", "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "archive" {
  name                        = var.archive_bucket_name
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
  lifecycle_rule {
    condition { days_since_noncurrent_time = var.archive_noncurrent_retention_days }
    action { type = "Delete" }
  }
  lifecycle { prevent_destroy = true }
  depends_on = [google_project_service.api]
}

resource "google_firestore_database" "reports" {
  name                              = var.firestore_database_name
  location_id                       = var.firestore_location
  type                              = "FIRESTORE_NATIVE"
  delete_protection_state           = "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = "ABANDON"
  point_in_time_recovery_enablement = var.firestore_pitr_enabled ? "POINT_IN_TIME_RECOVERY_ENABLED" : "POINT_IN_TIME_RECOVERY_DISABLED"
  lifecycle { prevent_destroy = true }
  depends_on = [google_project_service.api]
}

resource "google_service_account" "runtime" {
  account_id   = "artefacts-runtime"
  display_name = "Artefacts hosted backend"
  depends_on   = [google_project_service.api]
}

resource "google_storage_bucket_iam_member" "runtime" {
  bucket = google_storage_bucket.archive.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "database" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
  condition {
    title       = "Artefacts database only"
    expression  = "resource.name == 'projects/${var.gcp_project_id}/databases/${google_firestore_database.reports.name}'"
    description = "Restrict this runtime to its dedicated Firestore database."
  }
}
