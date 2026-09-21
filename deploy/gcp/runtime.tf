# IAM authentication is retained until the explicit public invocation switch is
# enabled. The hosted application independently validates Access JWTs on all routes.
resource "google_cloud_run_v2_service" "reports" {
  name                = "artefacts"
  location            = var.gcp_region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }
    containers {
      image = var.container_image
      ports { container_port = 8080 }
      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      env {
        name  = "ARTEFACTS_BUCKET"
        value = google_storage_bucket.archive.name
      }
      env {
        name  = "ARTEFACTS_DATABASE"
        value = google_firestore_database.reports.name
      }
      env {
        name  = "CLOUDFLARE_ACCESS_ISSUER"
        value = var.cloudflare_access_issuer
      }
      env {
        name  = "ARTEFACTS_OWNER_EMAILS"
        value = jsonencode(sort(tolist(var.owner_emails)))
      }
      env {
        name  = "ARTEFACTS_PUBLIC_ORIGIN"
        value = "https://artefacts.saunois.xyz"
      }
      env {
        name  = "CLOUDFLARE_ACCESS_AUDIENCE"
        value = cloudflare_zero_trust_access_application.reports.aud
      }
    }
  }
  depends_on = [google_project_service.api, google_project_iam_member.database, google_storage_bucket_iam_member.runtime]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.public_invocation_enabled ? 1 : 0
  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.reports.location
  name     = google_cloud_run_v2_service.reports.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
