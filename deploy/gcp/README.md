# Artefacts hosting foundations

This directory prepares `artefacts.saunois.xyz`. It is **not a deployable public
replacement for the local report server yet**. No resources have been created.
The GCP account, project, billing account and locations must be approved by Geoffrey
before planning against an account or applying anything.

## Infrastructure

- Cloud Run uses request-based CPU billing, minimum zero instances and an explicitly
  supplied maximum. Its image must be pinned by digest. There is no public invoker
  IAM binding: the service requires Google authentication even with public ingress.
- GCS stores published HTML, markdown sources and attachments privately. Versioning,
  public-access prevention and deletion protection protect the archive. Noncurrent
  versions expire after the explicitly supplied retention period.
- An explicitly selected Firestore database holds metadata, grants and comment
  transactions. Its runtime IAM binding is limited to this database. The database
  has deletion protection; point-in-time recovery is an explicit paid option.
- Cloudflare Access supplies email OTP and initially allows only explicit owners.
  Email delivery is Cloudflare's responsibility; no SMTP or Resend is required.
- No DNS record, origin routing, tunnel, load balancer, image repository or public
  service binding is provisioned by these foundations. The existing local server
  and its Cloudflare tunnel remain untouched.

Scale-to-zero covers compute, not storage. For a new dedicated personal project,
recommend `firestore_database_name = "(default)"` and
`firestore_pitr_enabled = false` at bootstrap, pending owner approval. A named
Firestore database is not entitled to the default database's free quota. GCS
versions consume storage until their explicit noncurrent retention expires;
Cloud Storage soft-delete retention can retain deleted versions longer. Confirm
these choices when selecting the project and retention policy.
The maximum instance count is a scaling setting, not a monetary spending cap.

## Required inputs and credentials

Every input in `variables.tf` is explicit. Supply a private, gitignored `.tfvars`
file after the account choice. Do not copy a work GCP project into this config.
Authenticate Google using ADC or workload identity; do not create a service-account
JSON key. Supply Cloudflare's scoped token through `CLOUDFLARE_API_TOKEN`.

Cloudflare bootstrap requires an existing Zero Trust organization and an active
Cloudflare zone for `saunois.xyz`. This stage needs Access application/policy and
identity-provider edit permissions. DNS permissions become necessary when adding
origin routing. Import existing matching Access/OTP resources if the account
already has them; do not create conflicting resources blindly.

The hosted backend image is an explicit prerequisite. The local entry point binds
loopback, serves the entire archive, attributes all browser comments to Geoffrey,
and uses POSIX file locks. It must not be passed as the hosted image.

## Backend integration before public traffic

1. Validate Cloudflare JWT signatures using the organization's JWKS; require the
   configured issuer, application audience, expiry, and verified email. A raw
   identity header is never proof of identity. Protect direct Cloud Run requests
   identically. Require the issuer/team domain explicitly in hosted configuration.
2. Implement a deny-by-default report grant model: owner, reader, commenter.
   Enforce it for the gallery, each HTML/source/file response and every comment
   operation. Store the authenticated author on comments; enforce edit/delete
   ownership. Unshared reports must not appear in catalog results.
3. Store pages and sources using the GCS API, and comments/grants in Firestore
   transactions. Do not mount the bucket over the POSIX store: its locking and
   atomic replacement semantics are not a distributed transaction protocol.
4. Provide authenticated publication and comment APIs for the local CLI. Migrate
   only selected reports with an explicit owner; review embedded comment snapshots
   in HTML because those snapshots are visible to every reader of that report.
5. Provide a sharing endpoint and UI. A future application-owned Cloudflare access
   group can contain the union of owners and active invitees. Terraform owns the
   application/policy and references the group; the application owns membership.
   Do not manage the same membership in Terraform and the API. Removing a report
   grant takes effect in the backend immediately, irrespective of Access sessions.
6. Choose and validate custom-domain routing/TLS. A Cloudflare DNS CNAME alone is
   not enough to configure the Cloud Run origin hostname and certificate. Compare
   a compatible domain mapping with a Cloudflare Worker proxy; avoid silently adding
   an always-on paid GCP load balancer. Disable caching of private report responses.
7. Only after auth and ACL tests pass, introduce public invocation plus the selected
   routing. Test OTP, direct-origin bypass, cross-report access, reader writes,
   revocation, concurrent comments, and persistence through scale-to-zero/restarts.

## Local validation

```sh
terraform -chdir=deploy/gcp init -backend=false -input=false
terraform -chdir=deploy/gcp fmt -check
terraform -chdir=deploy/gcp validate
```

These commands need no account credentials and create no cloud resources. Provider
versions are exact and `.terraform.lock.hcl` records their checksums. Google 7.26.0
was released March 31, 2026; Cloudflare 5.19.0 April 24, 2026. Both exceed the
30-day soak at preparation on September 21, 2026. This directory introduces no
Python dependencies. Account-specific planning and integration tests are pending.
A secured remote Terraform state backend must be selected before actual deployment.

References:
- https://github.com/hashicorp/terraform-provider-google/releases/tag/v7.26.0
- https://github.com/cloudflare/terraform-provider-cloudflare/releases/tag/v5.19.0
- https://docs.cloud.google.com/firestore/native/docs/manage-databases
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
