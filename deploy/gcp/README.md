# Artefacts hosted reports

`visualreport.hosted` serves selected reports from a private GCS bucket with
transactional metadata, permissions and comments in Firestore. It is separate from
the local archive server. No existing archive is automatically copied to GCP.

Cloudflare Access identifies users through email OTP. Anyone can authenticate, but
the application grants no report access until its owner shares that report. The
application validates the Access JWT signature, fixed issuer, audience and expiry
on requests arriving through Cloudflare and directly at the Cloud Run URL.
No SMTP or Resend is required. Terraform owns authentication infrastructure;
Firestore holds report permissions, so invitations do not require an apply.

## Runtime

Cloud Run minimum is zero; maximum is an explicit input. Request-based CPU billing
permits scale-to-zero. `public_invocation_enabled` explicitly controls whether
Cloud Run accepts unauthenticated invocations at its IAM layer; the hosted
application still requires a valid Access identity. A page kept open polls its
comments every four seconds and therefore counts as traffic.

GCS stores immutable HTML/source publications. Firestore transactions update each
report's grants and comment state. Authorization is rechecked in the transaction,
including author ownership for editing/deleting comments. Re-publication preserves
current comments/grants and re-homes anchors against the new source. HTML responses
replace the embedded comment snapshot with current comments and prohibit caching.
The gallery is filtered by permissions, and archive directories, raw sources,
logs and filesystem paths have no public routes.

Environment variables are all required:

| Name | Value |
|---|---|
| `GCP_PROJECT_ID` | approved project ID |
| `ARTEFACTS_BUCKET` | private GCS bucket |
| `ARTEFACTS_DATABASE` | explicit Firestore database name |
| `CLOUDFLARE_ACCESS_ISSUER` | `https://<team>.cloudflareaccess.com` |
| `CLOUDFLARE_ACCESS_AUDIENCE` | Access application audience |
| `ARTEFACTS_OWNER_EMAILS` | JSON array of administrator emails |
| `ARTEFACTS_PUBLIC_ORIGIN` | `https://artefacts.saunois.xyz` |
| `PORT` | supplied by Cloud Run |

The runtime uses GCP workload identity. Do not create service-account JSON keys.
Cloudflare's Terraform credential comes from `CLOUDFLARE_API_TOKEN`; the app needs
no Cloudflare administration token. Existing Access resources must be imported
before applying a matching configuration.

## Build and publication

From the repository root, build with an approved Python 3.14 Linux base image pinned
by digest, then pass the resulting image digest to Terraform:

```sh
docker build --platform linux/amd64 -f deploy/gcp/Dockerfile \
  --build-arg PYTHON_IMAGE="$REVIEWED_PYTHON_IMAGE" -t "$IMAGE_TAG" .
```

The Dockerfile installs only the hash-pinned runtime requirements. The service runs
as an unprivileged user on `0.0.0.0:$PORT`. The image contains code only, no archive
or credentials. It uses Cloud Run's TCP startup probe; `/api/health` is authenticated.

Publish only a specifically approved report, with its matching markdown source.
Set `ARTEFACTS_ACCESS_JWT` to an existing owner Access session token without putting
it into source control or command-line arguments. For example, after an interactive
Cloudflare login: `export ARTEFACTS_ACCESS_JWT="$(cloudflared access token --app=https://artefacts.saunois.xyz)"`.
CLI requests refuse redirects to prevent credential forwarding.

```sh
uv run --frozen python -m visualreport.hosted.publish \
  --origin https://artefacts.saunois.xyz \
  --page /absolute/path/report-demo-2026-09-21.html \
  --source /absolute/path/report-demo-2026-09-21.md --title 'Demo'

uv run --frozen python -m visualreport.hosted.share \
  --origin https://artefacts.saunois.xyz \
  --document report-demo --email alice@acme.fr --role commenter
```

Use `reader` for read-only access and `revoke` to remove a grant. Readers can see
all comments in that report; commenters can write and change their own comments.
Owners can manage grants and moderate/resolve/delete threads. Existing Access
sessions do not retain revoked report grants: each read checks Firestore again.
The commands print URLs/status, never tokens. No invitation email is sent; share
the report URL separately. A sharing button is not implemented yet. The existing
comment panel shows some actions that the backend will refuse for readers or
non-owning commenters; role-aware UI is a remaining usability improvement.

## Storage and cost

Select the project and billing account explicitly. For a fresh personal project,
`firestore_database_name = "(default)"` preserves eligibility for the free quota;
`firestore_pitr_enabled = false` avoids paid PITR at bootstrap. A named database
does not get the default database's free quota. GCS versions expire according to
`archive_noncurrent_retention_days`; default GCS soft-delete retention can retain
them longer. Published immutable objects are not automatically garbage-collected:
old publications remain current GCS objects until an explicit cleanup is implemented.
Review retention and costs before large migrations.

Report metadata and comments share a transactional Firestore document, limited by
the application to 700 KB; larger conversations return 413 rather than silently
losing data. HTML is limited to 8 million characters and markdown to 1 million.
Only the latest published version is exposed. Pages remain self-contained; external
attachments need a future owner-controlled publication route with report ACLs.

## Validation

```sh
uv run --frozen pytest -q
node --test tests/proxy.test.mjs
uv run --frozen ruff check src/visualreport/hosted tests/test_hosted.py
terraform -chdir=deploy/gcp init -backend=false -input=false
terraform -chdir=deploy/gcp fmt -check
terraform -chdir=deploy/gcp validate
```

JWT tests use real RSA signatures. Authorization tests cover unshared reports,
read-only users, author ownership, revocation including concurrent mutation,
publication ownership and cross-origin mutation refusal. The unit suite does not
replace a GCP smoke check for workload identity, transaction retries, bucket access,
OTP login, proxy/TLS, and persistence across restarts. Use a new non-confidential
smoke report before sharing real reports.

Provider versions and checksums are pinned. Runtime dependencies were resolved
with an August 20, 2026 release cutoff (>30 days before preparation) and audited.
Regenerate `requirements.txt` after changing the lock:

```sh
uv export --frozen --no-dev --no-emit-project --format requirements-txt > deploy/gcp/requirements.txt
```

## Durable Terraform state and deployment helper

The GCS backend in `state.tf` requires a pre-existing dedicated bucket. It must
not share the runtime archive bucket: the application identity has no state access.
Bootstrap with the explicit approved deployment account; do not apply the main
configuration until its existing local state has been migrated. Set the two
required tfvars: `terraform_state_bucket_name` and
`terraform_state_retention_days`. Bucket location uses the selected `gcp_region`.

Before changing the backend, make a durable, private backup outside Git and `/tmp`:

```sh
install -d -m 700 "$HOME/.local/share/artefacts"
install -m 600 deploy/gcp/terraform.tfstate \
  "$HOME/.local/share/artefacts/terraform-before-gcs.tfstate"
```

Use explicitly selected values for `ACCOUNT`, `PROJECT`, `REGION`, `STATE_BUCKET`,
`STATE_PREFIX` and `VARS` (the absolute JSON tfvars path). Do not infer the account
from the active gcloud configuration. The following are operator steps; the helper
does not silently create buckets, migrate state or start interactive authentication:

```sh
gcloud storage buckets create "gs://$STATE_BUCKET" \
  --account="$ACCOUNT" --project="$PROJECT" --location="$REGION" \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update "gs://$STATE_BUCKET" \
  --account="$ACCOUNT" --versioning
export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token --account="$ACCOUNT")"
terraform -chdir=deploy/gcp init -migrate-state \
  -backend-config="bucket=$STATE_BUCKET" -backend-config="prefix=$STATE_PREFIX"
terraform -chdir=deploy/gcp import -var-file="$VARS" \
  google_storage_bucket.terraform_state "$STATE_BUCKET"
terraform -chdir=deploy/gcp state list
```

Check that the remote state contains every resource from the local backup before
removing any local copy. Keep the private backup until a successful remote-state
plan/apply has completed. Protect the state bucket with narrow IAM; versioning
allows recovery and the GCS backend supplies locking. Terraform configures its
noncurrent-version retention on the next reviewed apply. A saved plan can contain
sensitive values: keep it outside Git, and review it before applying.

After bootstrap/migration, use the helper from the repository root:

```sh
deploy/gcp/deploy.sh plan \
  --account "$ACCOUNT" --project "$PROJECT" --vars "$VARS" \
  --secrets "$HOME/.secrets/cloudflare-artefacts.env" \
  --state-bucket "$STATE_BUCKET" --state-prefix "$STATE_PREFIX" \
  --plan "$HOME/.local/share/artefacts/deployment.tfplan"
```

Review the output, then repeat the exact command with `apply` instead of `plan`.
Apply executes the selected saved plan and verifies its project/state-bucket
variables. It never generates a replacement plan. Expired plans must be replanned
and reviewed. The helper uses `uv sync --frozen`, compares the exported runtime
requirements to the lock, validates Terraform and reads the Cloudflare token from
the explicit secret file. Google provider and backend use an ephemeral token for
`--account`, without changing active accounts or relying on another account's ADC.
