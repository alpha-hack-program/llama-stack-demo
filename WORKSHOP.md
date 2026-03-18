# Workshop Environment Setup

This guide explains how to create the environment for running the Llama Stack Demo workshop. For full installation details, see [README.md](README.md).

## Prerequisites

### OpenShift Cluster

- **OpenShift 4.20+** (tested on 4.20)
- **Red Hat OpenShift AI 3.2+** (includes Llama Stack Operator, OpenShift Service Mesh, OpenShift Serverless)

### Cluster Administrator Access

You must have **cluster-admin** privileges to install the operators required by Red Hat OpenShift AI. According to [Red Hat OpenShift AI 3.2 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.2/html-single/managing_openshift_ai/managing_openshift_ai), cluster administrator access is required to install Red Hat OpenShift AI and manage its components.

## Workshop Setup Script

Use `workshop-setup.sh` to create the full workshop environment: users (via htpasswd file), projects, group permissions, and node assignments.

### What It Does

1. **Generates htpasswd file** — Always runs `setup-htpasswd-oauth.sh` in dry-run mode. Writes the htpasswd file (default: `htpasswd.workshop`) and prints instructions for the Administrator to apply it manually to the cluster OAuth.
2. **Creates projects** — `llama-stack-demo-user1`, `llama-stack-demo-user2`, ... with labels `modelmesh-enabled=false` and `opendatahub.io/dashboard=true`.
3. **Creates group and permissions** — Creates group `workshop` with users `user1..userN`, grants each user admin and ServiceMonitor access on their project (idempotent; safe to re-run).
4. **Sets up monitoring and cluster resources** — Runs `setup-monitoring.sh` (Tempo, OTel, DSCI), `setup-hardware-profile.sh` (HardwareProfile in redhat-ods-applications), `setup-rbac.sh` (configmap-patcher ClusterRole/Role per namespace), and `setup-grafana-proxy-rbac.sh` (Grafana proxy RBAC per namespace).
5. **Assigns nodes** — Runs `assign-nodes-to-users.sh` to label one node per user (unless `--no-assign` is passed).

### Usage

```bash
./scripts/workshop-setup.sh [--dry-run] [--no-assign] <number_of_users> [password]
```

- `number_of_users` — Number of users (user1..userN) and projects to create
- `password` — Optional. If omitted, a random password is generated and shown in the output
- `--dry-run` — Preview all actions without making any changes
- `--no-assign` — Skip node assignment (useful when nodes are pre-assigned or not needed)
- `CUSTOM_PROJECT` — Optional env var (default: `llama-stack-demo`)
- `HTPASSWD_OUTPUT` — Optional env var for htpasswd file path (default: `htpasswd.workshop` in repo root)
- `INSTANCE_TYPE` — Optional env var for node assignment (default: `g5.2xlarge`); see [Instance Type](#instance-type-instance_type) below

### Administrator: Applying the htpasswd File

The script always generates the htpasswd file in dry-run mode. **You must apply it manually** to configure OAuth:

1. During Step 1 of `workshop-setup.sh`, the htpasswd file is written to `htpasswd.workshop` in the repository root (or the path in `HTPASSWD_OUTPUT`).
2. Follow the instructions printed by the script. Either:
   - **Option A (manual):** Create the secret and update OAuth:
     ```bash
     oc create secret generic htpasswd-secret --from-file=htpasswd=htpasswd.workshop -n openshift-config --dry-run=client -o yaml | oc apply -f -
     oc edit oauth cluster   # Add HTPasswd identity provider with htpasswd.fileData.name: htpasswd-secret
     ```
   - **Option B (automatic):** Run `setup-htpasswd-oauth.sh` without dry-run:
     ```bash
     ./scripts/setup-htpasswd-oauth.sh <number_of_users> <password>
     ```
     Use the password from the workshop-setup output if one was generated.

### Dry-Run (Safest)

Use `--dry-run` to preview all actions **without making any changes**:

```bash
./scripts/workshop-setup.sh --dry-run 5
```

**What dry-run does:**

- **Step 1:** Generates the htpasswd file and prints Administrator instructions — no secret or OAuth changes
- **Steps 2–4:** Skipped (no projects, group, or node assignment)

**After dry-run:**

1. Review the output to confirm user count, password, and project names
2. Run **without** `--dry-run` to create projects, group, and assign nodes:
   ```bash
   ./scripts/workshop-setup.sh 5 mypassword
   ```
3. Apply the htpasswd file using the instructions from Step 1 (see above)

### Skipping Node Assignment

If you do not need GPU node assignment (e.g. nodes are pre-configured or using a different setup):

```bash
./scripts/workshop-setup.sh --no-assign 5
```

### Instance Type (INSTANCE_TYPE)

When assigning nodes, the script filters nodes by Kubernetes instance type (e.g. `node.kubernetes.io/instance-type`). The default is `g5.2xlarge` (AWS GPU instance). If your cluster uses different GPU or instance types, set `INSTANCE_TYPE` before running:

```bash
export INSTANCE_TYPE="g5.2xlarge"   # default; AWS NVIDIA GPU
./scripts/workshop-setup.sh 5
```

Or when running `assign-nodes-to-users.sh` directly:

```bash
./scripts/assign-nodes-to-users.sh 5 g5.2xlarge
```

Common values: `g5.2xlarge` (AWS), `n1-standard-4` (GCP), `Standard_NC4as_T4_v3` (Azure).

### Idempotency

Steps 2–5 are idempotent. You can re-run the script (without `--dry-run`) and it will:

- Update labels on existing projects
- Add users to the group (no duplicates)
- Re-apply admin role bindings
- Assign nodes only for users that do not yet have one

## Next Steps

After workshop setup:

1. Each user logs in with `user1`..`userN` and the provided password
2. Each user installs the demo in their project:

   ```bash
   PROJECT="llama-stack-demo-user1"   # replace with userN
   helm install llama-stack-demo helm/ -f helm/values-workshop.yaml --set assigned="${PROJECT}" --namespace ${PROJECT} --timeout 20m
   ```

For GPU node assignment details, node labels, and other configuration, see [README.md](README.md).
