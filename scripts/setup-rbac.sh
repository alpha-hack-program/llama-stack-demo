#!/usr/bin/env bash
# Creates configmap-patcher RBAC, MLflow pipeline-runner RBAC for each workshop
# namespace, and Argo CD cluster RBAC. Run as cluster-admin before users install
# the Helm chart.
# These resources require cluster-admin because they include cluster-scoped
# ClusterRoles and resources in redhat-ods-applications namespace.
#
# Implementation: delegates to
#   - setup-rbac-configmap-patcher-cluster.sh (shared ClusterRole + ODS Role)
#   - setup-rbac-argocd.sh (Argo CD application manager)
#   - setup-rbac-for-user.sh (per ${CUSTOM_PROJECT}-userK namespace)
#
# Configmap-patcher:
#   ClusterRole: configmap-patcher-ingress-reader (shared)
#   ClusterRoleBinding: configmap-patcher-ingress-reader-${PROJECT} per namespace
#   Role in redhat-ods-applications: configmap-patcher-mcp-servers (shared)
#   RoleBinding in redhat-ods-applications: configmap-patcher-${PROJECT} per namespace
#
# MLflow (per namespace): Role and RoleBinding pipeline-runner-dspa-mlflow so
#   ServiceAccount pipeline-runner-dspa can access mlflow.kubeflow.org resources.
#
# Argo CD (cluster-wide):
#   ClusterRole argocd-application-manager + ClusterRoleBinding argocd-application-manager
#     (serviceaccounts, secrets, services, deployments, routes in all namespaces) so Argo CD can sync apps.
#
# Usage: setup-rbac.sh [--dry-run] <number_of_users>
# Env:   CUSTOM_PROJECT  Project/namespace prefix (default: llama-stack-demo)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUSTOM_PROJECT="${CUSTOM_PROJECT:-llama-stack-demo}"

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

echo "Creating configmap-patcher, MLflow, and Argo CD RBAC for ${NUM_USERS} namespace(s)..."
echo ""

export DRY_RUN
export CUSTOM_PROJECT

"$SCRIPT_DIR/setup-rbac-configmap-patcher-cluster.sh"
echo ""
"$SCRIPT_DIR/setup-rbac-argocd.sh"
echo ""

for (( i = 1; i <= NUM_USERS; i++ )); do
  PROJECT="${CUSTOM_PROJECT}-user${i}"
  "$SCRIPT_DIR/setup-rbac-for-user.sh" "$PROJECT"
done

echo ""
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run complete. Run without --dry-run to apply."
else
  echo "Done. configmap-patcher, MLflow, and Argo CD RBAC are pre-created (Argo CD bindings are cluster-wide)."
fi
