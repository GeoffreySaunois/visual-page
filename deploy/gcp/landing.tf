resource "cloudflare_dns_record" "landing" {
  zone_id = var.cloudflare_zone_id
  name    = "saunois.xyz"
  type    = "A"
  content = "76.76.21.21"
  ttl     = 300
  proxied = false
  comment = "Personal landing hosted on Vercel"
}
