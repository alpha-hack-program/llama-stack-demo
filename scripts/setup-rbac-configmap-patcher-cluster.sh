#!/usr/bin/env bash
# Creates shared (cluster-wide) configmap-patcher RBAC: one ClusterRole for ingress
# read and one Role in redhat-ods-applications for the gen-ai-aa-mcp-servers ConfigMap.
# Per-namespace bindings are in setup-rbac-for-user.sh.
# Run as cluster-admin.
#
# Usage: setup-rbac-configmap-patcher-cluster.sh [--dry-run]
#
# When invoked from setup-rbac.sh, DRY_RUN may be set in the environment (0/1) instead
# of passing --dry-run on the command line.

set -euo pipefail

ODS_NS="redhat-ods-applications"
CR_NAME="configmap-patcher-ingress-reader"
ROLE_NAME="configmap-patcher-mcp-servers"

usage() {
  echo "Usage: $0 [--dry-run]" >&2
  echo "  Creates shared ClusterRole and Role in ${ODS_NS} for configmap-patcher." >&2
  exit 1
}

DRY_RUN="${DRY_RUN:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Error: unknown argument: $1" >&2; usage ;;
  esac
done

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

echo "Applying configmap-patcher cluster RBAC (shared ClusterRole and ODS Role)..."

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
