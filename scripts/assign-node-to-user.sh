#!/usr/bin/env bash
# Assigns one node to a user by labelling a node of a given instance type.
# Portable: macOS (Bash 3.x) and Linux (Bash 4+).
# Nodes are labelled with ${CUSTOM_LABEL}=${CUSTOM_LABEL_PREFIX}-<sanitized_user>
# User input is sanitized to ASCII letters and numbers only (safe for k8s resources).
#
# Usage: assign-node-to-user.sh <user> [instance_type]
# Env:   CUSTOM_LABEL       label key (default: assigned)
#        CUSTOM_LABEL_PREFIX  label value prefix (default: llama-stack-demo)

set -euo pipefail

CUSTOM_LABEL="${CUSTOM_LABEL:-assigned}"
CUSTOM_LABEL_PREFIX="${CUSTOM_LABEL_PREFIX:-llama-stack-demo}"

usage() {
  echo "Usage: $0 <user> [instance_type]" >&2
  echo "  user           User identifier (will be sanitized: ASCII letters and numbers only)." >&2
  echo "  instance_type  Node instance type (default: g5.2xlarge)." >&2
  echo "" >&2
  echo "Optional env: CUSTOM_LABEL (default: assigned), CUSTOM_LABEL_PREFIX (default: llama-stack-demo)" >&2
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

USER="$1"
INSTANCE_TYPE="${2:-g5.2xlarge}"

# Sanitize user for k8s: ASCII letters and numbers only, no spaces nor special chars
# tr -dc removes all chars except those in the set; LC_ALL=C ensures ASCII
SANITIZED_USER=$(echo "$USER" | LC_ALL=C tr -dc 'a-zA-Z0-9' | tr '[:upper:]' '[:lower:]')

if [[ -z "$SANITIZED_USER" ]]; then
  echo "Error: user '$USER' yields empty string after sanitization (need at least one ASCII letter or digit)." >&2
  exit 1
fi

VALUE="${CUSTOM_LABEL_PREFIX}-${SANITIZED_USER}"

# Get nodes of this instance type that do NOT already have CUSTOM_LABEL
NODES_JSON=$(oc get nodes -l "node.kubernetes.io/instance-type=${INSTANCE_TYPE}" -o json 2>/dev/null) || {
  echo "Error: failed to get nodes (check 'oc' and cluster access)." >&2
  exit 2
}

# Check if this user already has a node assigned
EXISTING_NODE=$(echo "$NODES_JSON" | jq -r --arg key "$CUSTOM_LABEL" --arg val "$VALUE" '
  .items[] | select(.metadata.labels[$key] == $val) | .metadata.name
' | head -n1)

if [[ -n "$EXISTING_NODE" ]]; then
  echo "User '${SANITIZED_USER}' already has node: $EXISTING_NODE (${CUSTOM_LABEL}=${VALUE})"
  exit 0
fi

# Get first unassigned node
UNASSIGNED_NODE=$(echo "$NODES_JSON" | jq -r --arg key "$CUSTOM_LABEL" '
  .items[] | select(.metadata.labels[$key] == null or .metadata.labels[$key] == "") | .metadata.name
' | head -n1)

if [[ -z "$UNASSIGNED_NODE" ]]; then
  echo "Error: no unassigned nodes of instance type ${INSTANCE_TYPE} available." >&2
  exit 2
fi

if oc label node "$UNASSIGNED_NODE" "${CUSTOM_LABEL}=${VALUE}" --overwrite 2>/dev/null; then
  echo "Assigned $UNASSIGNED_NODE -> ${CUSTOM_LABEL}=${VALUE} (user: ${SANITIZED_USER})"
else
  echo "Error: failed to label node $UNASSIGNED_NODE" >&2
  exit 2
fi
