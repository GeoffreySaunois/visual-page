output "cloud_run_url" { value = google_cloud_run_v2_service.reports.uri }
output "archive_bucket" { value = google_storage_bucket.archive.name }
output "firestore_database" { value = google_firestore_database.reports.name }
output "cloudflare_access_audience" { value = cloudflare_zero_trust_access_application.reports.aud }
