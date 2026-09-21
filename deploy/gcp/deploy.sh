#!/usr/bin/env bash
# Plan and apply with explicit identities and a previously migrated GCS backend.
set -euo pipefail
umask 077

usage() {
  cat <<'HELP'
Usage: deploy.sh plan|apply \
  --account EMAIL --project ID --vars PATH --secrets PATH \
  --state-bucket NAME --state-prefix PREFIX --plan PATH

All arguments are required. Plan writes a reviewed plan file; apply executes that
same file without replanning. No login, account switching or backend migration is
performed. Bootstrap/migrate the backend using README.md before using this helper.
The secrets file exports CLOUDFLARE_API_TOKEN. Never put secrets into CLI arguments.
HELP
}

parse() {
  [[ $# -gt 0 ]] || { usage; exit 2; }
  [[ "$1" != --help ]] || { usage; exit 0; }
  action="$1"; shift
  [[ "$action" == plan || "$action" == apply ]] || { usage; exit 2; }
  while [[ $# -gt 0 ]]; do
    [[ $# -ge 2 ]] || { usage; exit 2; }
    case "$1" in
      --account) account="$2" ;; --project) project="$2" ;;
      --vars) vars="$2" ;; --secrets) secrets="$2" ;;
      --state-bucket) state_bucket="$2" ;; --state-prefix) state_prefix="$2" ;;
      --plan) plan="$2" ;; *) usage; exit 2 ;;
    esac
    shift 2
  done
}

require_inputs() {
  : "${account:?--account required}" "${project:?--project required}"
  : "${vars:?--vars required}" "${secrets:?--secrets required}"
  : "${state_bucket:?--state-bucket required}" "${state_prefix:?--state-prefix required}"
  : "${plan:?--plan required}"
  [[ -f "$vars" && -f "$secrets" ]] || { echo 'Vars/secrets file missing' >&2; exit 2; }
  [[ "$vars" == *.json ]] || { echo 'Use an explicit JSON tfvars file' >&2; exit 2; }
  vars="$(cd "$(dirname "$vars")" && pwd)/$(basename "$vars")"
  secrets="$(cd "$(dirname "$secrets")" && pwd)/$(basename "$secrets")"
  plan="$(cd "$(dirname "$plan")" && pwd)/$(basename "$plan")"
}

prepare_environment() {
  uv --directory "$repo" sync --frozen
  local exported
  exported="$(mktemp)"
  (cd "$repo" && uv export --frozen --no-dev --no-emit-project --format requirements-txt) > "$exported"
  if ! cmp -s "$exported" "$infra/requirements.txt"; then
    rm -f "$exported"; echo 'Runtime requirements differ from the frozen lock' >&2; exit 2
  fi
  rm -f "$exported"
  "$repo/.venv/bin/python" - "$vars" "$project" "$state_bucket" <<'PY'
import json, sys
values = json.load(open(sys.argv[1]))
if values.get('gcp_project_id') != sys.argv[2] or values.get('terraform_state_bucket_name') != sys.argv[3]:
    raise SystemExit('Explicit project/state bucket disagree with tfvars')
PY
}

credentials() {
  # Disable tracing before sourcing tokens, including if the caller used bash -x.
  set +x
  set -a
  source "$secrets"
  set +a
  : "${CLOUDFLARE_API_TOKEN:?Secret file must export CLOUDFLARE_API_TOKEN}"
  GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token --account="$account" --quiet)"
  unset GOOGLE_CREDENTIALS GOOGLE_APPLICATION_CREDENTIALS GOOGLE_IMPERSONATE_SERVICE_ACCOUNT
  unset GOOGLE_BACKEND_CREDENTIALS GOOGLE_BACKEND_IMPERSONATE_SERVICE_ACCOUNT
  export GOOGLE_OAUTH_ACCESS_TOKEN
  export TF_IN_AUTOMATION=1
}

initialize() {
  terraform -chdir="$infra" init -input=false -lockfile=readonly \
    -backend-config="bucket=$state_bucket" -backend-config="prefix=$state_prefix"
  terraform -chdir="$infra" fmt -check
  terraform -chdir="$infra" validate
}

apply_reviewed_plan() {
  [[ -f "$plan" ]] || { echo 'Saved plan file missing; run plan first' >&2; exit 2; }
  terraform -chdir="$infra" show -json "$plan" | "$repo/.venv/bin/python" -c '
import json, sys
variables = json.load(sys.stdin)["variables"]
if variables["gcp_project_id"]["value"] != sys.argv[1] or variables["terraform_state_bucket_name"]["value"] != sys.argv[2]:
    raise SystemExit("Saved plan targets a different project or state bucket")
' "$project" "$state_bucket"
  terraform -chdir="$infra" apply -input=false "$plan"
}

parse "$@"
require_inputs
infra="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$infra/../.." && pwd)"
prepare_environment
credentials
initialize
if [[ "$action" == plan ]]; then
  terraform -chdir="$infra" plan -input=false -var-file="$vars" -out="$plan"
  printf 'Review the plan above, then rerun with apply and the same --plan path.\n'
else
  apply_reviewed_plan
fi
