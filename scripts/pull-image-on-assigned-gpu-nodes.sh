#!/usr/bin/env bash
# Pre-pulls one or more container images on nodes you select either by:
#   - oc label selector (NODE_LABEL_SELECTOR or --label key=value), or
#   - assign-nodes-to-users.sh style labels (CUSTOM_LABEL / CUSTOM_LABEL_PREFIX).
# Uses oc debug + chroot host crictl. Run as a user who can create debug pods on
# those nodes (typically cluster-admin).
#
# Usage: pull-image-on-assigned-gpu-nodes.sh [--dry-run] [--label SELECTOR] [--parallel N] [image ...]
# Env:   NODE_LABEL_SELECTOR  If set (and no --label), use: oc get nodes -l SELECTOR
#        CUSTOM_LABEL         (default: assigned) — only when no label selector
#        CUSTOM_LABEL_PREFIX  (default: llama-stack-demo)
#        OC_REQUEST_TIMEOUT   Passed to oc --request-timeout (default: 0 = no limit)
#        PULL_PARALLEL        Max concurrent oc debug pulls (default: 4)

set -euo pipefail

CUSTOM_LABEL="${CUSTOM_LABEL:-assigned}"
CUSTOM_LABEL_PREFIX="${CUSTOM_LABEL_PREFIX:-llama-stack-demo}"
DEFAULT_IMAGE="registry.redhat.io/rhelai1/modelcar-qwen3-8b-fp8-dynamic:1.5"
OC_REQUEST_TIMEOUT="${OC_REQUEST_TIMEOUT:-0}"
PULL_PARALLEL="${PULL_PARALLEL:-4}"
# oc -l format, e.g. pulled=false or nvidia.com/gpu.present=true,pulled=false
NODE_LABEL_SELECTOR="${NODE_LABEL_SELECTOR:-}"

usage() {
  echo "Usage: $0 [--dry-run] [--label SELECTOR] [--parallel N] [image ...]" >&2
  echo "  --dry-run         List nodes and images; do not pull." >&2
  echo "  --label SELECTOR  Only nodes matching oc get nodes -l SELECTOR (e.g. pulled=false)." >&2
  echo "                    Overrides NODE_LABEL_SELECTOR for this run." >&2
  echo "  --parallel N      Run at most N pulls at once (default: ${PULL_PARALLEL})." >&2
  echo "  image ...         One or more full image references." >&2
  echo "                    If omitted, pulls only: ${DEFAULT_IMAGE}" >&2
  echo "" >&2
  echo "Without --label / NODE_LABEL_SELECTOR, nodes match \`${CUSTOM_LABEL}=<${CUSTOM_LABEL_PREFIX}-userN>\`" >&2
  echo "(same as assign-nodes-to-users.sh)." >&2
  echo "Env: NODE_LABEL_SELECTOR, CUSTOM_LABEL, CUSTOM_LABEL_PREFIX, OC_REQUEST_TIMEOUT, PULL_PARALLEL" >&2
  exit 1
}

DRY_RUN=0
IMAGES=()
SELECTOR="$NODE_LABEL_SELECTOR"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --label)
      if [[ $# -lt 2 ]]; then
        echo "Error: --label requires a selector (e.g. pulled=false)." >&2
        exit 1
      fi
      SELECTOR="$2"
      shift 2
      ;;
    --parallel)
      if [[ $# -lt 2 ]] || ! [[ "$2" =~ ^[1-9][0-9]*$ ]]; then
        echo "Error: --parallel requires a positive integer." >&2
        exit 1
      fi
      PULL_PARALLEL="$2"
      shift 2
      ;;
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

if ! [[ "$PULL_PARALLEL" =~ ^[1-9][0-9]*$ ]]; then
  echo "Error: PULL_PARALLEL must be a positive integer (got: ${PULL_PARALLEL})." >&2
  exit 1
fi

if ! command -v oc >/dev/null 2>&1; then
  echo "Error: oc not found in PATH." >&2
  exit 2
fi

NODES=()
if [[ -n "$SELECTOR" ]]; then
  node_list=$(oc get nodes -l "$SELECTOR" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}') || {
    echo "Error: failed to list nodes with -l ${SELECTOR} (check oc login and permissions)." >&2
    exit 2
  }
  while IFS= read -r name; do
    [[ -n "$name" ]] && NODES+=("$name")
  done < <(echo "$node_list" | sort -u)
  if [[ ${#NODES[@]} -eq 0 ]]; then
    echo "Error: no nodes match label selector: -l ${SELECTOR}" >&2
    exit 3
  fi
else
  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq not found in PATH (required unless NODE_LABEL_SELECTOR or --label is set)." >&2
    exit 2
  fi
  NODES_JSON=$(oc get nodes -o json) || {
    echo "Error: failed to list nodes (check oc login and permissions)." >&2
    exit 2
  }
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
    echo "Error: no nodes match ${CUSTOM_LABEL}=<${CUSTOM_LABEL_PREFIX}-userN> (run assign-nodes-to-users.sh first, use --label, or check labels)." >&2
    exit 3
  fi
fi

echo "Images (${#IMAGES[@]}):"
for img in "${IMAGES[@]}"; do
  echo "  $img"
done
echo "Nodes (${#NODES[@]}): ${NODES[*]}"
echo "Parallelism: up to ${PULL_PARALLEL} concurrent pull(s) per batch."
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

# Used for background pulls so failures still name node + image.
pull_one_job() {
  local node="$1"
  local image="$2"
  if ! pull_one "$node" "$image"; then
    echo "Error: pull failed on ${node} for ${image}" >&2
    return 1
  fi
}

TASK_NODES=()
TASK_IMAGES=()
for node in "${NODES[@]}"; do
  for image in "${IMAGES[@]}"; do
    TASK_NODES+=("$node")
    TASK_IMAGES+=("$image")
  done
done
ntasks=${#TASK_NODES[@]}

FAILED=0
i=0
while (( i < ntasks )); do
  pids=()
  for (( j = 0; j < PULL_PARALLEL && i < ntasks; j++, i++ )); do
    node="${TASK_NODES[i]}"
    image="${TASK_IMAGES[i]}"
    pull_one_job "$node" "$image" &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
      FAILED=1
    fi
  done
done

if [[ "$FAILED" -ne 0 ]]; then
  exit 4
fi

echo "Done."
