#!/usr/bin/env bash
# Creates Grafana proxy RBAC (ClusterRole, ClusterRoleBinding, RoleBinding) for each
# workshop namespace. Run as cluster-admin before users install the Helm chart.
# The Helm chart must use grafana.proxyRbac.create=false when RBAC is pre-created.
#
# Usage: setup-grafana-proxy-rbac.sh [--dry-run] <number_of_users>
# Env:   CUSTOM_PROJECT  Project/namespace prefix (default: llama-stack-demo)
#        APP_NAME        App name for SA reference (default: same as CUSTOM_PROJECT)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUSTOM_PROJECT="${CUSTOM_PROJECT:-llama-stack-demo}"
APP_NAME="${APP_NAME:-$CUSTOM_PROJECT}"

usage() {
  echo "Usage: $0 [--dry-run] <number_of_users>" >&2
  echo "  --dry-run       Preview actions without making changes." >&2
  echo "  number_of_users Number of namespaces (${CUSTOM_PROJECT}-user1..userN)." >&2
  echo "" >&2
  echo "Optional env: CUSTOM_PROJECT (default: llama-stack-demo), APP_NAME (default: same as CUSTOM_PROJECT)" >&2
  exit 1
}

DRY_RUN=0
NUM_USERS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    *)
      if [[ -z "$NUM_USERS" ]] && [[ "$1" =~ ^[0-9]+$ ]]; then
        NUM_USERS="$1"
      fi
      shift
      ;;
  esac
done

if [[ -z "$NUM_USERS" ]] || ! [[ "$NUM_USERS" =~ ^[0-9]+$ ]] || [[ "$NUM_USERS" -lt 1 ]]; then
  echo "Error: number_of_users must be a positive integer." >&2
  usage
fi

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

if [[ "$DRY_RUN" -eq 0 ]]; then
  if ! command -v oc &>/dev/null; then
    echo "Error: oc (OpenShift CLI) is required." >&2
    exit 2
  fi
  if ! oc whoami &>/dev/null; then
    echo "Error: you are not logged into OpenShift. Run 'oc login' and try again." >&2
    exit 2
  fi
fi

echo "Creating Grafana proxy RBAC for ${NUM_USERS} namespace(s)..."

for (( i = 1; i <= NUM_USERS; i++ )); do
  NS="${CUSTOM_PROJECT}-user${i}"
  CR_NAME="grafana-proxy-${NS}"
  CRB_NAME="grafana-proxy-${NS}"
  RB_NAME="${APP_NAME}-grafana-application-monitoring"
  SA_NAME="${APP_NAME}-grafana-sa"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  Would create ClusterRole ${CR_NAME}, ClusterRoleBinding ${CRB_NAME}, RoleBinding ${RB_NAME} in ${NS}"
    continue
  fi

  if ! oc get project "$NS" &>/dev/null; then
    echo "  Warning: namespace ${NS} does not exist; skipping." >&2
    continue
  fi

  # ClusterRole (unique per namespace)
  run oc apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: ${CR_NAME}
rules:
  - verbs: [create]
    apiGroups: [authentication.k8s.io]
    resources: [tokenreviews]
  - verbs: [create]
    apiGroups: [authorization.k8s.io]
    resources: [subjectaccessreviews]
EOF

  # ClusterRoleBinding (unique per namespace)
  run oc apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: ${CRB_NAME}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: ${CR_NAME}
subjects:
  - kind: ServiceAccount
    name: ${SA_NAME}
    namespace: ${NS}
EOF

  # RoleBinding in namespace (links cluster-monitoring-view to Grafana SA)
  run oc apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ${RB_NAME}
  namespace: ${NS}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-monitoring-view
subjects:
  - kind: ServiceAccount
    name: ${SA_NAME}
    namespace: ${NS}
EOF

  echo "  Created RBAC for ${NS}"
done

echo ""
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run complete. Run without --dry-run to apply."
else
  echo "Done. Helm chart must use grafana.proxyRbac.create=false (e.g. -f helm/values-workshop.yaml)."
fi
