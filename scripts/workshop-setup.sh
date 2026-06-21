#!/usr/bin/env bash
# Creates workshop environment: generates htpasswd file (admin applies manually),
# creates projects, workshop group with permissions, and optionally assigns nodes.
#
# Usage: workshop-setup.sh [--dry-run] [--no-assign] <number_of_users> [password]
# Env:   CUSTOM_PROJECT  Project name prefix (default: llama-stack-demo)
#
# Step 1: Generates the htpasswd file ONLY (raw user:hash lines) plus a companion
#         README with instructions. NEVER creates/updates the htpasswd Secret nor
#         modifies oauth/cluster. Applying it is a separate, explicit admin action.
# Step 2: Creates projects (${CUSTOM_PROJECT}-user1, ...) with labels.
# Step 3: Creates group "workshop", adds users, grants admin per project (idempotent).
# Step 4: Runs setup-user-workload-monitoring.sh, setup-monitoring.sh, setup-hardware-profile.sh,
#         setup-minio.sh, setup-mlflow.sh, setup-rbac.sh, and setup-grafana-proxy-rbac.sh.
#         Each sub-step self-skips when its operator/feature is absent or already
#         present, so re-runs are safe and partial clusters won't hard-fail.
# Step 5: Runs assign-nodes-to-users.sh unless --no-assign is passed.
#
# Projects: ${CUSTOM_PROJECT}-user1, ${CUSTOM_PROJECT}-user2, ...
# Labels:   modelmesh-enabled=false opendatahub.io/dashboard=true

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CUSTOM_PROJECT="${CUSTOM_PROJECT:-llama-stack-demo}"
GROUP_NAME="${GROUP_NAME:-workshop}"
HTPASSWD_OUTPUT="${HTPASSWD_OUTPUT:-$REPO_ROOT/htpasswd.workshop}"
HTPASSWD_SECRET_NAME="${HTPASSWD_SECRET_NAME:-htpasswd-secret}"
HTPASSWD_SECRET_NAMESPACE="${HTPASSWD_SECRET_NAMESPACE:-openshift-config}"

# True if the cluster serves the given API group (i.e. the operator/CRD is
# installed). Uses a targeted discovery call so it is reliable even when an
# unrelated aggregated APIService is degraded (oc api-resources can flake then).
api_group_available() { oc get --raw "/apis/$1" >/dev/null 2>&1; }

usage() {
  echo "Usage: $0 [--dry-run] [--no-assign] <number_of_users> [password]" >&2
  echo "  --dry-run       Preview all actions without making changes." >&2
  echo "  --no-assign     Skip node assignment (assign-nodes-to-users.sh)." >&2
  echo "  number_of_users Number of users (user1..userN) and projects." >&2
  echo "  password        Optional. Password for all users (default: generated)." >&2
  echo "" >&2
  echo "Optional env: CUSTOM_PROJECT (default: llama-stack-demo), HTPASSWD_OUTPUT (default: htpasswd.workshop), INSTANCE_TYPE (default: g5.2xlarge)" >&2
  exit 1
}

DRY_RUN=0
NO_ASSIGN=0
NUM_USERS=""
PASSWORD_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)   DRY_RUN=1; shift ;;
    --no-assign) NO_ASSIGN=1; shift ;;
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

if ! [[ "$NUM_USERS" =~ ^[0-9]+$ ]] || [[ "$NUM_USERS" -lt 1 ]]; then
  echo "Error: number_of_users must be a positive integer." >&2
  usage
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

  # Check required permissions (cluster-admin or equivalent)
  MISSING_PERMS=()
  oc auth can-i create projectrequest &>/dev/null || MISSING_PERMS+=("create projectrequest")
  oc auth can-i create groups &>/dev/null || MISSING_PERMS+=("create groups")
  oc auth can-i create rolebindings --all-namespaces &>/dev/null || MISSING_PERMS+=("create rolebindings")
  oc auth can-i create clusterroles &>/dev/null || MISSING_PERMS+=("create clusterroles")
  oc auth can-i create clusterrolebindings &>/dev/null || MISSING_PERMS+=("create clusterrolebindings")
  if [[ "$NO_ASSIGN" -eq 0 ]]; then
    oc auth can-i patch nodes &>/dev/null || MISSING_PERMS+=("patch nodes")
  fi
  if [[ ${#MISSING_PERMS[@]} -gt 0 ]]; then
    echo "Error: insufficient permissions. Missing: ${MISSING_PERMS[*]}" >&2
    echo "This script requires cluster-admin or equivalent. Run 'oc login' as a cluster administrator." >&2
    exit 2
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "=== DRY RUN: No changes will be made ==="
  echo ""
fi

# -----------------------------------------------------------------------------
# Step 1: Generate htpasswd file (always dry-run) and give admin instructions
# -----------------------------------------------------------------------------
echo "Step 1: Generating htpasswd file for user1..user${NUM_USERS}..."
export HTPASSWD_OUTPUT
htpasswd_output=$("$SCRIPT_DIR/setup-htpasswd-oauth.sh" --dry-run --silent "$NUM_USERS" ${PASSWORD_ARG:+"$PASSWORD_ARG"} 2>/dev/null)
eval "$htpasswd_output"
DISPLAY_PASSWORD="${PASSWORD_ARG:-${HTPASSWD_PASSWORD:-}}"

# Companion README next to the htpasswd file. This is purely informational —
# nothing here is applied. The raw htpasswd file is left comment-free so it
# stays valid as Secret data.
HTPASSWD_README="${HTPASSWD_OUTPUT}.README.txt"
PASSWORD_LINE="(password you provided)"
[[ -n "$DISPLAY_PASSWORD" ]] && PASSWORD_LINE="$DISPLAY_PASSWORD"
cat > "$HTPASSWD_README" <<EOF
Generated by workshop-setup.sh on $(date '+%Y-%m-%d %H:%M:%S %Z')
NOT applied to the cluster. No Secret and no OAuth configuration was modified.

These users (user1..user${NUM_USERS}) all share the same password:
  ${PASSWORD_LINE}

The raw htpasswd lines were written to:
  ${HTPASSWD_OUTPUT}

To make these users usable, an administrator must apply them manually
(as cluster-admin). This is a separate, explicit action:

  1. Create/update the Secret '${HTPASSWD_SECRET_NAME}' in namespace '${HTPASSWD_SECRET_NAMESPACE}':
       oc create secret generic ${HTPASSWD_SECRET_NAME} \\
         --from-file=htpasswd=${HTPASSWD_OUTPUT} \\
         -n ${HTPASSWD_SECRET_NAMESPACE} --dry-run=client -o yaml | oc apply -f -

  2. Add/ensure an HTPasswd identity provider in oauth/cluster:
       oc edit oauth cluster
     with an identityProvider of type: HTPasswd and
     htpasswd.fileData.name: ${HTPASSWD_SECRET_NAME}

Updating the Secret/OAuth does NOT invalidate existing sessions; only new
logins use the new configuration.
EOF

echo ""
echo "--- htpasswd: NO changes were made to the Secret or OAuth ---"
echo "Generated (not applied):"
echo "  htpasswd file: ${HTPASSWD_OUTPUT}"
echo "  instructions:  ${HTPASSWD_README}"
[[ -n "$DISPLAY_PASSWORD" ]] && echo "  password:      ${DISPLAY_PASSWORD} (shared by user1..user${NUM_USERS})"
echo ""
echo "To apply later (separate, explicit admin action — see the README above):"
echo "  oc create secret generic ${HTPASSWD_SECRET_NAME} --from-file=htpasswd=${HTPASSWD_OUTPUT} -n ${HTPASSWD_SECRET_NAMESPACE} --dry-run=client -o yaml | oc apply -f -"
echo "  then add an HTPasswd identityProvider (htpasswd.fileData.name: ${HTPASSWD_SECRET_NAME}) to oauth/cluster."
echo "---"
echo ""

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Step 2-5 skipped (dry-run)."
  echo ""
  echo "=== Dry-run summary ==="
  echo "  Users:     user1..user${NUM_USERS}"
  echo "  Htpasswd:  ${HTPASSWD_OUTPUT}"
  echo "  Readme:    ${HTPASSWD_README}"
  [[ -n "$DISPLAY_PASSWORD" ]] && echo "  Password:  ${DISPLAY_PASSWORD}" || true
  echo ""
  echo "Run without --dry-run to create projects, group, and assign nodes."
  exit 0
fi

# -----------------------------------------------------------------------------
# Step 2: Create projects and label them
# -----------------------------------------------------------------------------
echo "Step 2: Creating projects and applying labels..."
for (( i = 1; i <= NUM_USERS; i++ )); do
  PROJECT="${CUSTOM_PROJECT}-user${i}"
  if oc get project "$PROJECT" &>/dev/null; then
    echo "  Project ${PROJECT} already exists, updating labels..."
  else
    echo "  Creating project ${PROJECT}..."
    oc new-project "$PROJECT" >/dev/null
  fi
  oc label namespace "$PROJECT" modelmesh-enabled=false opendatahub.io/dashboard=true --overwrite
  echo "  Labeled ${PROJECT}"
done

echo ""

# -----------------------------------------------------------------------------
# Step 3: Create group and assign permissions (idempotent)
# -----------------------------------------------------------------------------
export CUSTOM_PROJECT GROUP_NAME
"$SCRIPT_DIR/create-workshop-group.sh" "$NUM_USERS"

echo ""

# -----------------------------------------------------------------------------
# Step 4: Setup monitoring, MLflow, and Grafana proxy RBAC
# -----------------------------------------------------------------------------
# Pre-flight: report what is already present so it is clear up front which
# sub-steps will be skipped (each sub-script also self-skips when absent).
echo "Pre-flight — detected on cluster (steps for absent/already-present features are skipped):"
if oc get configmap cluster-monitoring-config -n openshift-monitoring -o jsonpath='{.data.config\.yaml}' 2>/dev/null | grep -qE '^[[:space:]]*enableUserWorkload:[[:space:]]*true'; then
  echo "  - User Workload Monitoring: already enabled"
else
  echo "  - User Workload Monitoring: not enabled (will enable)"
fi
api_group_available tempo.grafana.com         && echo "  - Tempo operator:        present"          || echo "  - Tempo operator:        absent (Tempo step skipped)"
api_group_available opentelemetry.io          && echo "  - OpenTelemetry operator: present"         || echo "  - OpenTelemetry operator: absent (OTel/Instrumentation steps skipped)"
api_group_available infrastructure.opendatahub.io && echo "  - HardwareProfile CRD:   present"     || echo "  - HardwareProfile CRD:   absent (hardware-profile step skipped)"
api_group_available argoproj.io               && echo "  - Argo CD (GitOps):      present"          || echo "  - Argo CD (GitOps):      absent (MinIO step skipped)"
api_group_available mlflow.opendatahub.io     && echo "  - MLflow operator:       present"          || echo "  - MLflow operator:       absent (MLflow step skipped)"
api_group_available grafana.integreatly.org   && echo "  - Grafana operator:      present (optional Grafana dashboards available with helm --set monitoring.enable=true)" \
                                              || echo "  - Grafana operator:      absent (Grafana dashboards are OFF by default; install it to opt in via monitoring.enable=true)"
echo ""

echo "Step 4: Enabling user workload monitoring, then monitoring stack, hardware profile, MinIO, MLflow, configmap-patcher RBAC, and Grafana proxy RBAC..."
export CUSTOM_PROJECT
"$SCRIPT_DIR/setup-user-workload-monitoring.sh"
"$SCRIPT_DIR/setup-monitoring.sh"
"$SCRIPT_DIR/setup-hardware-profile.sh"
"$SCRIPT_DIR/setup-minio.sh"
"$SCRIPT_DIR/setup-mlflow.sh"
"$SCRIPT_DIR/setup-rbac.sh" "$NUM_USERS"
"$SCRIPT_DIR/setup-grafana-proxy-rbac.sh" "$NUM_USERS"
echo ""

# -----------------------------------------------------------------------------
# Step 5: Assign nodes to users (unless --no-assign)
# -----------------------------------------------------------------------------
if [[ "$NO_ASSIGN" -eq 0 ]]; then
  echo "Step 5: Assigning nodes to users..."
  export CUSTOM_LABEL_PREFIX="$CUSTOM_PROJECT"
  INSTANCE_TYPE="${INSTANCE_TYPE:-g5.2xlarge}"
  "$SCRIPT_DIR/assign-nodes-to-users.sh" --summary "$NUM_USERS" "$INSTANCE_TYPE"
else
  echo "Step 5: Skipped (--no-assign)."
fi

echo ""
echo "=== Workshop setup complete ==="
echo ""
echo "Summary:"
echo "  Users:     user1..user${NUM_USERS}"
echo "  Projects:  ${CUSTOM_PROJECT}-user1..user${NUM_USERS}"
echo "  Group:     ${GROUP_NAME}"
echo "  Htpasswd:  ${HTPASSWD_OUTPUT} (NOT applied — see ${HTPASSWD_README})"
[[ -n "$DISPLAY_PASSWORD" ]] && echo "  Password:  ${DISPLAY_PASSWORD}" || true
echo ""
echo "Next: Apply htpasswd to OAuth manually (this script did NOT — see ${HTPASSWD_README}), then each user runs:"
echo "  PROJECT=\"${CUSTOM_PROJECT}-user<N>\""
echo "  helm install llama-stack-demo helm/ -f helm/values-workshop.yaml --set assigned=\"\${PROJECT}\" --namespace \${PROJECT} --timeout 20m"
