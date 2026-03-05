#!/usr/bin/env bash
# Creates a group "workshop" with users user1-userN and grants each user admin
# permissions on their project so they can run:
#   helm install llama-stack-demo helm/ --set assigned="${PROJECT}" --namespace ${PROJECT} --timeout 20m
#
# Projects must exist (e.g. llama-stack-demo-user1, llama-stack-demo-user2, ...).
# Run workshop-setup.sh first to create users and projects.
#
# Usage: create-workshop-group.sh <number_of_users> [--create-projects]
# Env:   CUSTOM_PROJECT  Project name prefix (default: llama-stack-demo)

set -euo pipefail

CUSTOM_PROJECT="${CUSTOM_PROJECT:-llama-stack-demo}"
GROUP_NAME="${GROUP_NAME:-workshop}"

usage() {
  echo "Usage: $0 <number_of_users> [--create-projects]" >&2
  echo "  number_of_users  Number of users (user1..userN) to add to group ${GROUP_NAME}." >&2
  echo "  --create-projects  Create projects if they do not exist (default: assume they exist)." >&2
  echo "" >&2
  echo "Optional env: CUSTOM_PROJECT (default: llama-stack-demo), GROUP_NAME (default: workshop)" >&2
  exit 1
}

CREATE_PROJECTS=0
NUM_USERS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --create-projects) CREATE_PROJECTS=1; shift ;;
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

if ! command -v oc &>/dev/null; then
  echo "Error: oc (OpenShift CLI) is required." >&2
  exit 2
fi

if ! oc whoami &>/dev/null; then
  echo "Error: you are not logged into OpenShift. Run 'oc login' and try again." >&2
  exit 2
fi

echo "Creating group '${GROUP_NAME}' with users user1..user${NUM_USERS}..."

# Create group if it does not exist
if ! oc get group "$GROUP_NAME" &>/dev/null; then
  oc adm groups new "$GROUP_NAME"
fi

# Build user list and add to group
USER_LIST=()
for (( i = 1; i <= NUM_USERS; i++ )); do
  USER_LIST+=("user${i}")
done
oc adm groups add-users "$GROUP_NAME" "${USER_LIST[@]}"

echo "Group '${GROUP_NAME}' updated."

# Create projects if requested
for (( i = 1; i <= NUM_USERS; i++ )); do
  PROJECT="${CUSTOM_PROJECT}-user${i}"
  if [[ "$CREATE_PROJECTS" -eq 1 ]]; then
    if ! oc get project "$PROJECT" &>/dev/null; then
      echo "Creating project ${PROJECT}..."
      oc new-project "$PROJECT"
      oc label namespace "$PROJECT" modelmesh-enabled=false opendatahub.io/dashboard=true --overwrite
    fi
  else
    if ! oc get project "$PROJECT" &>/dev/null; then
      echo "Warning: project ${PROJECT} does not exist. Run workshop-setup.sh first or use --create-projects." >&2
      continue
    fi
  fi

  # Grant user admin on their project so they can run helm install
  echo "Granting user${i} admin on ${PROJECT}..."
  oc adm policy add-role-to-user admin "user${i}" -n "$PROJECT"

  # Grant ServiceMonitor access in namespace only (required for Helm chart ServiceMonitors)
  echo "Granting user${i} ServiceMonitor access on ${PROJECT}..."
  oc apply -f - <<EOF
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: servicemonitor-editor
  namespace: ${PROJECT}
rules:
  - apiGroups: ["monitoring.coreos.com"]
    resources: ["servicemonitors"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: servicemonitor-editor-user${i}
  namespace: ${PROJECT}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: servicemonitor-editor
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: User
    name: user${i}
EOF
done

echo ""
echo "Done. Users in group '${GROUP_NAME}' can run:"
echo "  helm install llama-stack-demo helm/ --set assigned=\"\${PROJECT}\" --namespace \${PROJECT} --timeout 20m"
echo ""
echo "Each user (user1..user${NUM_USERS}) has admin and ServiceMonitor access on their project (${CUSTOM_PROJECT}-user1..user${NUM_USERS})."
