#!/usr/bin/env bash
# Generates an htpasswd file with N users, creates an OpenShift secret from it,
# and configures the cluster OAuth to use the HTPasswd identity provider.
#
# Usage: setup-htpasswd-oauth.sh [--dry-run|--no-update] [--silent] <number_of_users> [password]
# Env:   HTPASSWD_SECRET_NAME  Secret name in openshift-config (default: htpasswd-secret)
#        HTPASSWD_IDP_NAME     OAuth identity provider name (default: htpasswd)
#        HTPASSWD_PASSWORD     Password for all users (overridden by [password]; if unset, one is generated)
#        HTPASSWD_OUTPUT       In dry-run, write htpasswd file to this path (default: htpasswd.dry-run)

set -euo pipefail

HTPASSWD_SECRET_NAME="${HTPASSWD_SECRET_NAME:-htpasswd-secret}"
HTPASSWD_IDP_NAME="${HTPASSWD_IDP_NAME:-htpasswd}"

usage() {
  echo "Usage: $0 [--dry-run|--no-update] [--silent] <number_of_users> [password]" >&2
  echo "  --dry-run, --no-update  Generate htpasswd file only; do not create secret or update OAuth." >&2
  echo "  --silent                Suppress informational output (for use when called from other scripts)." >&2
  echo "  number_of_users         Number of users to create in the htpasswd file (e.g. 5 → user1..user5)." >&2
  echo "  password                Optional. Password for all users. If omitted, a random 8-char (letters, numbers, 1 special) is generated." >&2
  echo "" >&2
  echo "Optional env: HTPASSWD_SECRET_NAME, HTPASSWD_IDP_NAME, HTPASSWD_PASSWORD, HTPASSWD_OUTPUT (dry-run output file)" >&2
  exit 1
}

DRY_RUN=0
SILENT=0
NUM_USERS=""
PASSWORD_ARG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|--no-update) DRY_RUN=1; shift ;;
    --silent) SILENT=1; shift ;;
    *)
      if [[ -z "$NUM_USERS" ]]; then
        NUM_USERS="$1"
      elif [[ -z "$PASSWORD_ARG" ]]; then
        PASSWORD_ARG="$1"
      fi
      shift
      ;;
  esac
done

if [[ -z "$NUM_USERS" ]]; then
  usage
fi

# Password: parameter > env > generated (8 ASCII: letters and numbers only, safe for eval/shell)
generate_password() {
  local letters='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
  local digits='0123456789'
  local pool="${letters}${digits}"
  local combined=""
  for (( i = 0; i < 8; i++ )); do
    combined+="${pool:$((RANDOM % ${#pool})):1}"
  done
  printf '%s' "$combined"
}

PASSWORD_WAS_GENERATED=0
if [[ -n "$PASSWORD_ARG" ]]; then
  HTPASSWD_PASSWORD="$PASSWORD_ARG"
elif [[ -n "${HTPASSWD_PASSWORD:-}" ]]; then
  :
else
  HTPASSWD_PASSWORD=$(generate_password)
  PASSWORD_WAS_GENERATED=1
fi

if ! [[ "$NUM_USERS" =~ ^[0-9]+$ ]] || [[ "$NUM_USERS" -lt 1 ]]; then
  echo "Error: number_of_users must be a positive integer." >&2
  usage
fi

# Check dependencies
if ! command -v htpasswd &>/dev/null; then
  echo "Error: htpasswd is required (install httpd-tools or apache2-utils)." >&2
  exit 2
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  if ! command -v oc &>/dev/null; then
    echo "Error: oc (OpenShift CLI) is required." >&2
    exit 2
  fi

  if ! oc whoami &>/dev/null; then
    echo "Error: you are not logged into OpenShift. Run 'oc login' and try again." >&2
    exit 2
  fi

  # Safety: Changing OAuth IdP or the htpasswd secret does not invalidate your current
  # session; your token remains valid. Only new logins use the updated configuration.
  # Check for existing OAuth HTPasswd configuration and confirm before replacing
  OAUTH_JSON=$(oc get oauth cluster -o json 2>/dev/null) || {
    echo "Error: failed to get OAuth cluster (cluster may not support OAuth or you may lack permissions)." >&2
    exit 2
  }
  HAS_HTPASSWD=$(echo "$OAUTH_JSON" | jq '[.spec.identityProviders[]? | select(.type == "HTPasswd")] | length')
  if [[ "${HAS_HTPASSWD:-0}" -gt 0 ]]; then
    echo "This cluster already has an HTPasswd OAuth identity provider configured."
    echo "Replacing it will update the secret and OAuth to use the new user list."
    read -r -p "Replace existing HTPasswd OAuth configuration? [y/N] " confirm
    case "${confirm:-n}" in
      [yY]|[yY][eE][sS]) ;;
      *) echo "Aborted. No changes made." >&2; exit 0 ;;
    esac
  fi
fi

# Where to write htpasswd: persistent file in dry-run, temp dir otherwise
if [[ "$DRY_RUN" -eq 1 ]]; then
  HTPASSWD_FILE="${HTPASSWD_OUTPUT:-htpasswd.dry-run}"
else
  TMPDIR_htpasswd=$(mktemp -d)
  trap 'rm -rf "$TMPDIR_htpasswd"' EXIT
  HTPASSWD_FILE="${TMPDIR_htpasswd}/htpasswd"
fi

msg() { [[ "$SILENT" -eq 0 ]] && echo "$@" || true; }
run_htpasswd() {
  if [[ "$SILENT" -eq 1 ]]; then
    htpasswd "$@" 2>/dev/null
  else
    htpasswd "$@"
  fi
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  msg "Dry run: generating htpasswd file only (no secret or OAuth update)."
  msg ""
fi
msg "Creating htpasswd file with ${NUM_USERS} user(s)..."

for (( i = 1; i <= NUM_USERS; i++ )); do
  username="user${i}"
  if [[ $i -eq 1 ]]; then
    run_htpasswd -c -B -b "$HTPASSWD_FILE" "$username" "$HTPASSWD_PASSWORD"
  else
    run_htpasswd -B -b "$HTPASSWD_FILE" "$username" "$HTPASSWD_PASSWORD"
  fi
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  if [[ "$SILENT" -eq 1 ]]; then
    echo "HTPASSWD_FILE=${HTPASSWD_FILE}"
    if [[ "$PASSWORD_WAS_GENERATED" -eq 1 ]]; then
      echo "HTPASSWD_PASSWORD=${HTPASSWD_PASSWORD}"
    fi
  else
    echo ""
    echo "Done (dry run). HTPasswd file written to: ${HTPASSWD_FILE}"
    echo ""
    echo "Users (${NUM_USERS}):"
    for (( i = 1; i <= NUM_USERS; i++ )); do
      echo "  user${i} / ${HTPASSWD_PASSWORD}"
    done
    if [[ "$PASSWORD_WAS_GENERATED" -eq 1 ]]; then
      echo ""
      echo "Generated password (save it): ${HTPASSWD_PASSWORD}"
    fi
    echo ""
    echo "To apply later: create the secret and update OAuth (run this script without --dry-run)."
  fi
  exit 0
fi

# Updating the OAuth IdP or htpasswd secret does NOT invalidate your current session.
# Your existing token stays valid until it expires; only new logins use the new IdP/secret.
msg "Creating/updating secret ${HTPASSWD_SECRET_NAME} in openshift-config..."
oc create secret generic "$HTPASSWD_SECRET_NAME" --from-file=htpasswd="$HTPASSWD_FILE" -n openshift-config --dry-run=client -o yaml | oc apply -f -

msg "Updating OAuth cluster to use HTPasswd identity provider..."

# Refresh OAuth spec (may have changed) and ensure we have exactly one HTPasswd idp (ours)
OAUTH_JSON=$(oc get oauth cluster -o json)

# Remove any existing HTPasswd identity provider(s), then add ours
OAUTH_PATCHED=$(echo "$OAUTH_JSON" | jq --arg idp_name "$HTPASSWD_IDP_NAME" --arg secret_name "$HTPASSWD_SECRET_NAME" '
  .spec.identityProviders |= (
    map(select(.type != "HTPasswd")) +
    [{
      name: $idp_name,
      type: "HTPasswd",
      challenge: true,
      login: true,
      mappingMethod: "claim",
      htpasswd: {
        fileData: {
          name: $secret_name
        }
      }
    }]
  )
')

echo "$OAUTH_PATCHED" | oc apply -f -

msg ""
msg "Done. HTPasswd OAuth has been successfully updated with ${NUM_USERS} user(s):"
for (( i = 1; i <= NUM_USERS; i++ )); do
  msg "  user${i} / ${HTPASSWD_PASSWORD}"
done
if [[ "$PASSWORD_WAS_GENERATED" -eq 1 ]]; then
  msg ""
  msg "Generated password (save it): ${HTPASSWD_PASSWORD}"
fi
msg ""
msg "Users can log in with: oc login -u user<N> -p ${HTPASSWD_PASSWORD} <cluster_api_url>"
