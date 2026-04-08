#!/usr/bin/env bash
# Pre-pulls one or more container images on every node labelled by assign-nodes-to-users.sh
# (same CUSTOM_LABEL / CUSTOM_LABEL_PREFIX). Uses oc debug + chroot host crictl.
# Run as a user who can create debug pods on those nodes (typically cluster-admin).
#
# Usage: pull-image-on-assigned-gpu-nodes.sh [--dry-run] [image ...]
# Env:   CUSTOM_LABEL         (default: assigned)
#        CUSTOM_LABEL_PREFIX  (default: llama-stack-demo)
#        OC_REQUEST_TIMEOUT   Passed to oc --request-timeout (default: 0 = no limit)

set -euo pipefail

CUSTOM_LABEL="${CUSTOM_LABEL:-assigned}"
CUSTOM_LABEL_PREFIX="${CUSTOM_LABEL_PREFIX:-llama-stack-demo}"
DEFAULT_IMAGE="registry.redhat.io/rhelai1/modelcar-qwen3-8b-fp8-dynamic:1.5"
OC_REQUEST_TIMEOUT="${OC_REQUEST_TIMEOUT:-0}"

usage() {
  echo "Usage: $0 [--dry-run] [image ...]" >&2
  echo "  --dry-run  List nodes and images; do not pull." >&2
  echo "  image ...  One or more full image references." >&2
  echo "             If omitted, pulls only: ${DEFAULT_IMAGE}" >&2
  echo "" >&2
  echo "Nodes are those with label \`${CUSTOM_LABEL}=<prefix>-user<N>\` (same as assign-nodes-to-users.sh)." >&2
  echo "Env: CUSTOM_LABEL, CUSTOM_LABEL_PREFIX, OC_REQUEST_TIMEOUT" >&2
  exit 1
}

DRY_RUN=0
IMAGES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage ;;
    -*)
      echo "Error: unknown option $1" >&2
      usage
      ;;
    *)
      IMAGES+=("$1")
      shift
      ;;
  esac
done

if [[ ${#IMAGES[@]} -eq 0 ]]; then
  IMAGES=("$DEFAULT_IMAGE")
fi

if ! command -v oc >/dev/null 2>&1; then
  echo "Error: oc not found in PATH." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq not found in PATH." >&2
  exit 2
fi

NODES_JSON=$(oc get nodes -o json) || {
  echo "Error: failed to list nodes (check oc login and permissions)." >&2
  exit 2
}

NODES=()
while IFS= read -r name; do
  [[ -n "$name" ]] && NODES+=("$name")
done < <(
  echo "$NODES_JSON" | jq -r --arg key "$CUSTOM_LABEL" --arg prefix "$CUSTOM_LABEL_PREFIX" '
    .items[]
    | .metadata.name as $n
    | (.metadata.labels[$key] // "") as $v
    | select($v != "" and ($v | test("^" + $prefix + "-user[0-9]+$")))
    | $n
  ' | sort -u
)

if [[ ${#NODES[@]} -eq 0 ]]; then
  echo "Error: no nodes match ${CUSTOM_LABEL}=<${CUSTOM_LABEL_PREFIX}-userN> (run assign-nodes-to-users.sh first, or check labels)." >&2
  exit 3
fi

echo "Images (${#IMAGES[@]}):"
for img in "${IMAGES[@]}"; do
  echo "  $img"
done
echo "Nodes (${#NODES[@]}): ${NODES[*]}"
echo ""

pull_one() {
  local node="$1"
  local image="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] oc debug node/${node} -- chroot /host crictl pull ${image}"
    return 0
  fi
  echo "Pulling on ${node}: ${image}"
  oc --request-timeout="$OC_REQUEST_TIMEOUT" debug "node/${node}" --quiet -- \
    chroot /host crictl pull "$image"
}

FAILED=0
for node in "${NODES[@]}"; do
  for image in "${IMAGES[@]}"; do
    if ! pull_one "$node" "$image"; then
      echo "Error: pull failed on ${node} for ${image}" >&2
      FAILED=1
    fi
  done
done

if [[ "$FAILED" -ne 0 ]]; then
  exit 4
fi

echo "Done."
