#!/usr/bin/env bash
# Creates cluster-wide Argo CD RBAC: argocd-application-manager ClusterRole and
# ClusterRoleBinding to the openshift-gitops application controller service account
# so Argo CD can sync applications.
# Run as cluster-admin.
#
# Usage: setup-rbac-argocd.sh [--dry-run]
#
# When invoked from setup-rbac.sh, DRY_RUN may be set in the environment (0/1) instead
# of passing --dry-run on the command line.

set -euo pipefail

ARGOCD_NS="openshift-gitops"
ARGOCD_SA="openshift-gitops-argocd-application-controller"

usage() {
  echo "Usage: $0 [--dry-run]" >&2
  echo "  Creates Argo CD application manager ClusterRole and ClusterRoleBinding." >&2
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

echo "Applying Argo CD cluster RBAC (argocd-application-manager)..."

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "  Would create ClusterRole and ClusterRoleBinding argocd-application-manager"
else
  run oc apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argocd-application-manager
rules:
- apiGroups: [""]
  resources:
  - serviceaccounts
  - secrets
  - services
  verbs:
  - get
  - list
  - watch
  - create
  - update
  - patch
  - delete
- apiGroups: ["apps"]
  resources:
  - deployments
  verbs:
  - get
  - list
  - watch
  - create
  - update
  - patch
  - delete
- apiGroups: ["route.openshift.io"]
  resources:
  - routes
  verbs:
  - get
  - list
  - watch
  - create
  - update
  - patch
  - delete
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argocd-application-manager
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: argocd-application-manager
subjects:
- kind: ServiceAccount
  name: ${ARGOCD_SA}
  namespace: ${ARGOCD_NS}
EOF
fi
