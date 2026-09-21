variable "cloudflare_zone_id" {
  description = "Cloudflare zone containing artefacts.saunois.xyz."
  type        = string
}

resource "cloudflare_workers_script" "reports" {
  account_id         = var.cloudflare_account_id
  script_name        = "artefacts-proxy"
  main_module        = "proxy.js"
  content            = file("${path.module}/proxy.js")
  compatibility_date = "2026-08-01"
  bindings = [{
    name = "BACKEND_ORIGIN"
    type = "plain_text"
    text = google_cloud_run_v2_service.reports.uri
  }]
}

resource "cloudflare_workers_script_subdomain" "reports" {
  account_id       = var.cloudflare_account_id
  script_name      = cloudflare_workers_script.reports.script_name
  enabled          = false
  previews_enabled = false
}

resource "cloudflare_workers_custom_domain" "reports" {
  account_id = var.cloudflare_account_id
  zone_id    = var.cloudflare_zone_id
  hostname   = "artefacts.saunois.xyz"
  service    = cloudflare_workers_script.reports.script_name
  depends_on = [cloudflare_zero_trust_access_application.reports]
}

resource "google_project_service" "artifact_registry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "reports" {
  location      = var.gcp_region
  repository_id = "artefacts"
  description   = "Reviewed backend images for personal visual reports"
  format        = "DOCKER"
  mode          = "STANDARD_REPOSITORY"
  depends_on    = [google_project_service.artifact_registry]
  lifecycle { prevent_destroy = true }
}
