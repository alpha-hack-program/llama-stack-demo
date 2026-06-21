#!/usr/bin/env bash
# Applies the cluster-scoped MLflow CR (mlflow.opendatahub.io/v1) once.
# The manifest has no namespace; -n must not be used. Run as cluster-admin from workshop-setup.sh
# so MLflow exists before users install the Helm chart.
#
# Usage: setup-mlflow.sh [--dry-run]
# Env:   MANIFESTS_DIR   Directory containing mlflow.yaml (default: scripts/resources)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${MANIFESTS_DIR:-$SCRIPT_DIR/resources}"

usage() {
  echo "Usage: $0 [--dry-run]" >&2
  echo "  --dry-run       Preview actions without making changes." >&2
  echo "" >&2
  echo "Optional env: MANIFESTS_DIR (default: scripts/resources)" >&2
  exit 1
}

DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Error: unknown argument: $1" >&2; usage ;;
  esac
done

MLFLOW_MANIFEST="${MANIFESTS_DIR}/mlflow.yaml"
if [[ ! -f "$MLFLOW_MANIFEST" ]]; then
  echo "Error: MLflow manifest not found: $MLFLOW_MANIFEST" >&2
  exit 1
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

# Skip when the MLflow operator (CRD) is not installed.
api_group_available() { oc get --raw "/apis/$1" >/dev/null 2>&1; }
if [[ "$DRY_RUN" -eq 0 ]] && ! api_group_available mlflow.opendatahub.io; then
  echo "MLflow operator not installed (no mlflow.opendatahub.io API group); skipping MLflow CR."
  echo "Install the MLflow operator, then re-run."
  exit 0
fi

echo "Applying cluster-scoped MLflow CR..."
run oc apply -f "$MLFLOW_MANIFEST"
if [[ "$DRY_RUN" -eq 0 ]]; then
  echo "Applied MLflow CR (cluster-scoped)."
fi

echo ""
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run complete. Run without --dry-run to apply."
else
  echo "Done. The MLflow operator will reconcile the cluster-scoped MLflow instance."
fi
