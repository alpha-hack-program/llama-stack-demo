#!/usr/bin/env bash
# Creates configmap-patcher RBAC (ClusterRole, ClusterRoleBinding, Role, RoleBinding)
# for each workshop namespace. Run as cluster-admin before users install the Helm chart.
# These resources require cluster-admin because they include cluster-scoped ClusterRoles
# and resources in redhat-ods-applications namespace.
#
# ClusterRole name: configmap-patcher-ingress-reader (shared)
# ClusterRoleBinding: configmap-patcher-ingress-reader-${PROJECT} per namespace
# Role in redhat-ods-applications: configmap-patcher-mcp-servers (shared, reused)
# RoleBinding in redhat-ods-applications: configmap-patcher-${PROJECT} per namespace
#
# Usage: setup-rbac.sh [--dry-run] <number_of_users>
# Env:   CUSTOM_PROJECT  Project/namespace prefix (default: llama-stack-demo)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUSTOM_PROJECT="${CUSTOM_PROJECT:-llama-stack-demo}"
ODS_NS="redhat-ods-applications"
SA_NAME="configmap-patcher"
CR_NAME="configmap-patcher-ingress-reader"
ROLE_NAME="configmap-patcher-mcp-servers"

usage() {
  echo "Usage: $0 [--dry-run] <number_of_users>" >&2
  echo "  --dry-run       Preview actions without making changes." >&2
  echo "  number_of_users Number of namespaces (${CUSTOM_PROJECT}-user1..userN)." >&2
  echo "" >&2
  echo "Optional env: CUSTOM_PROJECT (default: llama-stack-demo)" >&2
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

echo "Creating configmap-patcher RBAC for ${NUM_USERS} namespace(s)..."

# Single shared ClusterRole (ingress read)
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "  Would create ClusterRole ${CR_NAME}"
else
  run oc apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: ${CR_NAME}
rules:
  - apiGroups: ["config.openshift.io"]
    resources: ["ingresses"]
    verbs: ["get"]
EOF
fi

# Single shared Role in redhat-ods-applications (ConfigMap access)
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "  Would create Role ${ROLE_NAME} in ${ODS_NS}"
else
  run oc apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ${ROLE_NAME}
  namespace: ${ODS_NS}
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["create"]
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["gen-ai-aa-mcp-servers"]
    verbs: ["get", "list", "patch", "update"]
EOF
fi

for (( i = 1; i <= NUM_USERS; i++ )); do
  PROJECT="${CUSTOM_PROJECT}-user${i}"
  CRB_NAME="${CR_NAME}-${PROJECT}"
  RB_NAME="configmap-patcher-${PROJECT}"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  Would create ClusterRoleBinding ${CRB_NAME}, RoleBinding ${RB_NAME} in ${ODS_NS} for ${PROJECT}"
    continue
  fi

  if ! oc get project "$PROJECT" &>/dev/null; then
    echo "  Warning: namespace ${PROJECT} does not exist; skipping." >&2
    continue
  fi

  # ClusterRoleBinding: bind ClusterRole to configmap-patcher SA in user namespace
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
    namespace: ${PROJECT}
EOF

  # RoleBinding in redhat-ods-applications (binds shared Role to SA in user namespace)
  run oc apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ${RB_NAME}
  namespace: ${ODS_NS}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: ${ROLE_NAME}
subjects:
  - kind: ServiceAccount
    name: ${SA_NAME}
    namespace: ${PROJECT}
EOF

  echo "  Created RBAC for ${PROJECT}"
done

echo ""
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run complete. Run without --dry-run to apply."
else
  echo "Done. configmap-patcher RBAC is pre-created for workshop namespaces."
fi
