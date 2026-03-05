#!/usr/bin/env bash
# Creates the HardwareProfile in redhat-ods-applications namespace.
# This is a cluster-wide resource (not per-user) required by OpenShift AI for
# GPU scheduling. Run as cluster-admin during workshop setup.
#
# Usage: setup-hardware-profile.sh [--dry-run]
# Env:   MANIFEST_PATH  Path to hardware-profile.yaml (default: scripts/resources/hardware-profile.yaml)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_PATH="${MANIFEST_PATH:-$SCRIPT_DIR/resources/hardware-profile.yaml}"
NAMESPACE="redhat-ods-applications"

usage() {
  echo "Usage: $0 [--dry-run]" >&2
  echo "  --dry-run  Preview actions without making changes." >&2
  echo "" >&2
  echo "Optional env: MANIFEST_PATH (default: scripts/resources/hardware-profile.yaml)" >&2
  exit 1
}

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "Error: manifest not found: $MANIFEST_PATH" >&2
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
fi

echo "Creating HardwareProfile in ${NAMESPACE}..."

# Ensure namespace exists (OpenShift AI operator typically creates it)
if [[ "$DRY_RUN" -eq 0 ]] && ! oc get namespace "$NAMESPACE" &>/dev/null; then
  echo "Creating namespace ${NAMESPACE}..."
  run oc create namespace "$NAMESPACE"
fi

run oc apply -f "$MANIFEST_PATH"

echo ""
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run complete. Run without --dry-run to apply."
else
  echo "Done. HardwareProfile 'nvidia' is in ${NAMESPACE}."
fi
