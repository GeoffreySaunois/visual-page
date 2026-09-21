terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.26.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "5.19.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Read from CLOUDFLARE_API_TOKEN; never put credentials in tfvars.
provider "cloudflare" {}
