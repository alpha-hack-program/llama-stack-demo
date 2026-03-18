#!/usr/bin/env bash
# Creates an MLflow instance (Open Data Hub MLflow CR) in each workshop namespace.
# Run as cluster-admin from workshop-setup.sh so MLflow exists before users install the Helm chart.
#
# Usage: setup-mlflow.sh [--dry-run] <number_of_users>
# Env:   CUSTOM_PROJECT  Project/namespace prefix (default: llama-stack-demo)
#        MANIFESTS_DIR   Directory containing mlflow.yaml (default: scripts/resources)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CUSTOM_PROJECT="${CUSTOM_PROJECT:-llama-stack-demo}"
MANIFESTS_DIR="${MANIFESTS_DIR:-$SCRIPT_DIR/resources}"

usage() {
  echo "Usage: $0 [--dry-run] <number_of_users>" >&2
  echo "  --dry-run       Preview actions without making changes." >&2
  echo "  number_of_users Number of namespaces (${CUSTOM_PROJECT}-user1..userN)." >&2
  echo "" >&2
  echo "Optional env: CUSTOM_PROJECT (default: llama-stack-demo), MANIFESTS_DIR (default: scripts/resources)" >&2
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

echo "Creating MLflow instance in ${NUM_USERS} namespace(s)..."

for (( i = 1; i <= NUM_USERS; i++ )); do
  NS="${CUSTOM_PROJECT}-user${i}"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  Would apply MLflow in namespace ${NS}"
    continue
  fi

  if ! oc get project "$NS" &>/dev/null; then
    echo "  Warning: namespace ${NS} does not exist; skipping." >&2
    continue
  fi

  run oc apply -f "$MLFLOW_MANIFEST" -n "$NS"
  echo "  Applied MLflow in ${NS}"
done

echo ""
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run complete. Run without --dry-run to apply."
else
  echo "Done. MLflow instance (mlflow.opendatahub.io) will be created in each namespace by the operator."
fi
