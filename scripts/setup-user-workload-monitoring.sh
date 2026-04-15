#!/usr/bin/env bash
# Enables OpenShift User Workload Monitoring (UWM) via cluster-monitoring-config.
# Idempotent: creates the ConfigMap if absent, or merges enableUserWorkload: true
# into existing data.config.yaml without dropping other keys.
#
# Usage: ./scripts/setup-user-workload-monitoring.sh [--dry-run] [--no-wait]
# Env:   UWM_WAIT_SEC  Seconds to sleep before listing UWM pods (default: 30)

set -euo pipefail

MON_NS="openshift-monitoring"
CM_NAME="cluster-monitoring-config"
UWM_NS="openshift-user-workload-monitoring"
UWM_WAIT_SEC="${UWM_WAIT_SEC:-30}"

usage() {
  echo "Usage: $0 [--dry-run] [--no-wait]" >&2
  echo "  --dry-run   Print actions only (no cluster changes)." >&2
  echo "  --no-wait   Do not sleep or list pods in ${UWM_NS}." >&2
  echo "" >&2
  echo "Optional env: UWM_WAIT_SEC (default: 30)" >&2
  exit 1
}

DRY_RUN=0
NO_WAIT=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --no-wait) NO_WAIT=1; shift ;;
    -h|--help) usage ;;
    *) echo "Error: unknown option $1" >&2; usage ;;
  esac
done

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

# Returns merged config.yaml on stdout; exit 1 if already enabled (caller treats as skip).
merge_enable_user_workload() {
  local cfg="$1"
  if echo "$cfg" | grep -qE '^[[:space:]]*enableUserWorkload:[[:space:]]*true([[:space:]]|$|#)'; then
    return 1
  fi
  if echo "$cfg" | grep -qE '^[[:space:]]*enableUserWorkload:'; then
    echo "$cfg" | awk '
      /^[[:space:]]*enableUserWorkload:/ && !done { print "enableUserWorkload: true"; done=1; next }
      { print }
    '
    return 0
  fi
  if ! echo "$cfg" | grep -q '[^[:space:]]'; then
    printf '%s\n' "enableUserWorkload: true"
    return 0
  fi
  printf '%s\n%s\n' "enableUserWorkload: true" "$cfg"
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

echo "User Workload Monitoring: ConfigMap ${CM_NAME} in ${MON_NS}"
echo ""

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] Would ensure enableUserWorkload: true in ${MON_NS}/${CM_NAME} (create or merge)."
  if [[ "$NO_WAIT" -eq 0 ]]; then
    echo "[dry-run] Would sleep ${UWM_WAIT_SEC}s and run: oc get pods -n ${UWM_NS}"
  fi
  exit 0
fi

if ! oc get namespace "$MON_NS" &>/dev/null; then
  echo "Error: namespace ${MON_NS} not found (not an OpenShift cluster?)." >&2
  exit 2
fi

if ! oc get configmap "$CM_NAME" -n "$MON_NS" &>/dev/null; then
  echo "ConfigMap ${CM_NAME} does not exist; creating with enableUserWorkload: true..."
  run oc apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${CM_NAME}
  namespace: ${MON_NS}
data:
  config.yaml: |
    enableUserWorkload: true
EOF
else
  echo "ConfigMap ${CM_NAME} already exists; merging enableUserWorkload into config.yaml..."
  existing_cfg="$(oc get configmap "$CM_NAME" -n "$MON_NS" -o jsonpath='{.data.config\.yaml}' 2>/dev/null || true)"
  merged_file="$(mktemp "${TMPDIR:-/tmp}/cluster-monitoring-config-merged.XXXXXX")"
  trap 'rm -f "$merged_file"' EXIT
  if merge_enable_user_workload "$existing_cfg" > "$merged_file" 2>/dev/null; then
    if ! command -v jq &>/dev/null; then
      echo "Error: jq is required to patch an existing ConfigMap. Install jq or merge enableUserWorkload manually." >&2
      exit 2
    fi
    new_cfg="$(cat "$merged_file")"
    patch_json="$(jq -n --arg c "$new_cfg" '{data:{"config.yaml":$c}}')"
    run oc patch configmap "$CM_NAME" -n "$MON_NS" --type=merge -p "$patch_json"
  else
    echo "enableUserWorkload is already true; no change needed."
  fi
  rm -f "$merged_file"
  trap - EXIT
fi

echo ""

if [[ "$NO_WAIT" -eq 0 ]]; then
  echo "Waiting ${UWM_WAIT_SEC}s for the user-workload monitoring stack to reconcile..."
  sleep "$UWM_WAIT_SEC"
  echo ""
  echo "Pods in ${UWM_NS}:"
  if oc get namespace "$UWM_NS" &>/dev/null; then
    oc get pods -n "$UWM_NS" || true
  else
    echo "  Namespace ${UWM_NS} not present yet. The operator may still be creating it; check again shortly:" >&2
    echo "    oc get pods -n ${UWM_NS}" >&2
  fi
fi

echo ""
echo "Done. User Workload Monitoring is enabled (or was already)."
