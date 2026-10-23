resource "cloudflare_zero_trust_access_identity_provider" "email" {
  account_id = var.cloudflare_account_id
  name       = "Artefacts email code"
  type       = "onetimepin"
  config     = {}
}

resource "cloudflare_zero_trust_access_application" "reports" {
  account_id                = var.cloudflare_account_id
  name                      = "Artefacts"
  domain                    = "artefacts.saunois.xyz"
  type                      = "self_hosted"
  session_duration          = "720h"
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.email.id]
  auto_redirect_to_identity = true
  policies = [{
    name       = "Authenticated email identities"
    decision   = "allow"
    precedence = 1
    include    = [{ everyone = {} }]
    require    = [{ login_method = { id = cloudflare_zero_trust_access_identity_provider.email.id } }]
  }]
}
