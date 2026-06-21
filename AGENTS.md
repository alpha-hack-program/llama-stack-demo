# Llama Stack Demo — Deployment Runbook

Cluster: `api.ocp.sandbox2758.opentlc.com`
Model: Qwen3 8B FP8 Dynamic on NVIDIA A10G (`g5.2xlarge`)
Values file for workshop deployments: `helm/values-workshop.yaml`

---

## Prerequisites

- `oc` logged in as cluster-admin (`oc login --server=https://api.ocp.sandbox2758.opentlc.com:6443`)
- `helm` 3.x installed
- RHOAI operator installed and DSCI/DSC in Ready state (`oc get dsci,dsc -A`)
- ArgoCD (`openshift-gitops`) installed — required by `setup-minio.sh`

Verify before proceeding:

```bash
oc whoami
oc get dsci,dsc -A
oc get nodes -l node-role.kubernetes.io/gpu-worker
```

---

## Phase 1 — Workshop Setup (cluster-admin, run once)

### 1a. Dry-run preview

```bash
./scripts/workshop-setup.sh --dry-run 3
```

Reviews user count, generated password, and project names without making changes.

### 1b. Run setup

```bash
./scripts/workshop-setup.sh 3 <password>
```

Replace `3` with the number of users. If `<password>` is omitted a random one is generated and printed.

**What this does:**
1. Generates `htpasswd.workshop` (raw `user1..userN` lines) **and** `htpasswd.workshop.README.txt` with apply instructions. It does **not** create/update any Secret or modify `oauth/cluster` — applying is a separate, explicit admin action (see Phase 1c).
2. Creates projects `llama-stack-demo-user1..userN` labeled `modelmesh-enabled=false opendatahub.io/dashboard=true`
3. Creates group `workshop`, adds users, grants per-project admin
4. Runs in order: `setup-user-workload-monitoring.sh`, `setup-monitoring.sh` (Tempo + OTel + DSCI patch), `setup-hardware-profile.sh`, `setup-minio.sh` (ArgoCD Application → `minio` namespace), `setup-mlflow.sh`, `setup-rbac.sh`, `setup-grafana-proxy-rbac.sh`. Each sub-step **self-skips** when its operator/feature is absent or the resource already exists (a "Pre-flight — detected on cluster" summary is printed first), so re-runs are safe and a partially-provisioned cluster won't hard-fail. In particular, `setup-minio.sh` is skipped automatically if OpenShift GitOps (Argo CD) is not installed.
5. Labels one GPU node per user (`g5.2xlarge` by default)

**Skip node assignment** (if nodes are already labeled):

```bash
./scripts/workshop-setup.sh --no-assign 3 <password>
```

**Custom instance type:**

```bash
export INSTANCE_TYPE="g5.2xlarge"
./scripts/workshop-setup.sh 3 <password>
```

### 1c. Apply htpasswd to OAuth

`workshop-setup.sh` only **generates** `htpasswd.workshop` and `htpasswd.workshop.README.txt`; it never touches the htpasswd Secret or `oauth/cluster`. The steps below are the explicit, manual action that actually configures login — run them as cluster-admin once you're ready. The shared password and these same commands are also recorded in `htpasswd.workshop.README.txt`.

The script prints instructions. Either run:

```bash
oc create secret generic htpasswd-secret \
  --from-file=htpasswd=htpasswd.workshop \
  -n openshift-config --dry-run=client -o yaml | oc apply -f -
```

Then add/update the HTPasswd identity provider in `oc edit oauth cluster` (`htpasswd.fileData.name: htpasswd-secret`).

Or apply automatically:

```bash
./scripts/setup-htpasswd-oauth.sh 3 <password>
```

### 1d. Verify monitoring is ready

```bash
./scripts/check-monitoring-telemetry.sh
# or lenient mode right after setup:
./scripts/check-monitoring-telemetry.sh --lenient
```

---

## Phase 2 — Pre-pull Images on GPU Nodes (recommended)

Pulls model and vLLM images onto GPU nodes so the first deploy doesn't wait on registry pulls.

```bash
./scripts/pull-image-on-assigned-gpu-nodes.sh \
  registry.redhat.io/rhelai1/modelcar-qwen3-8b-fp8-dynamic:1.5 \
  registry.redhat.io/rhaiis/vllm-cuda-rhel9@sha256:ec799bb5eeb7e25b4b25a8917ab5161da6b6f1ab830cbba61bba371cffb0c34d
```

Pull pipeline runtime images on worker nodes:

```bash
./scripts/pull-image-on-assigned-gpu-nodes.sh \
  quay.io/modh/odh-pipeline-runtime-pytorch-cuda-py312-ubi9@sha256:72ff2381e5cb24d6f549534cb74309ed30e92c1ca80214669adb78ad30c5ae12 \
  --label node.kubernetes.io/instance-type=m7i.2xlarge,node-role.kubernetes.io/worker \
  --parallel 8
```

---

## Phase 3 — Deploy per User

Each user (or the admin on their behalf) runs this in their project:

```bash
PROJECT="llama-stack-demo-user1"   # replace with userN

helm install llama-stack-demo helm/ \
  -f helm/values-workshop.yaml \
  --set assigned="${PROJECT}" \
  --namespace ${PROJECT} \
  --timeout 20m
```

**With a secrets file** (remote models with API tokens):

```bash
helm install llama-stack-demo helm/ \
  -f helm/values-workshop.yaml \
  -f helm/values-secrets.yaml \
  --set assigned="${PROJECT}" \
  --namespace ${PROJECT} \
  --timeout 20m
```

**Upgrade an existing release:**

```bash
helm upgrade llama-stack-demo helm/ \
  -f helm/values-workshop.yaml \
  --set assigned="${PROJECT}" \
  --namespace ${PROJECT} \
  --timeout 20m
```

**Disable pipelines** (if Minio is not available):

```bash
helm install llama-stack-demo helm/ \
  -f helm/values-workshop.yaml \
  --set assigned="${PROJECT}" \
  --set pipelines.enabled=false \
  --namespace ${PROJECT} \
  --timeout 20m
```

**Observability / dashboards (optional):** Telemetry collection (ServiceMonitors,
Tempo/OTel/Prometheus) is always on and needs nothing extra. The Grafana dashboard
objects are **off by default** (`monitoring.enable: false`) because they require the
community **Grafana Operator**, which is not part of OpenShift/RHOAI. Opt in only on a
cluster where that operator is installed by adding `--set monitoring.enable=true`.
(The documented forward path is Perses via the Cluster Observability Operator — planned
as a separate effort; see README → Monitoring.)

---

## Phase 4 — Verify Deployment

### Watch pods come up (5–10 minutes)

```bash
oc -n ${PROJECT} get pods -w
```

Expected pods when healthy:

```
llama-stack-demo-0                   1/1  Running
llama-stack-demo-app-xxxxx           1/1  Running
llama-stack-demo-api-xxxxx           1/1  Running
eligibility-engine-xxxxx             1/1  Running
compatibility-engine-xxxxx           1/1  Running
cluster-insights-xxxxx               1/1  Running
finance-engine-xxxxx                 1/1  Running
milvus-standalone-xxxxx              1/1  Running
etcd-deployment-xxxxx                1/1  Running
attu-xxxxx                           1/1  Running
pg-lsd-xxxxx                         1/1  Running
cloudbeaver-xxxxx                    1/1  Running
qwen3-8b-fp8-dynamic-predictor-xxx   2/2  Running
```

### Get routes

```bash
# Streamlit UI
oc get route ${PROJECT}-app -n ${PROJECT} -o jsonpath='{.spec.host}'

# FastAPI
oc get route ${PROJECT}-api -n ${PROJECT} -o jsonpath='{.spec.host}'

# Llama Stack API
oc get route ${PROJECT}-route -n ${PROJECT} -o jsonpath='{.spec.host}'

# RHOAI Dashboard
oc get route rhods-dashboard -n redhat-ods-applications -o jsonpath='{.spec.host}'

# Attu (Milvus UI)
oc get route attu -n ${PROJECT} -o jsonpath='{.spec.host}'

# CloudBeaver (PostgreSQL UI)
oc get route cloudbeaver -n ${PROJECT} -o jsonpath='{.spec.host}'
```

---

## Demo — Example Queries

Use these in the Streamlit app with the system prompt below.

**System prompt:**
```
You are a helpful AI assistant that uses tools to help citizens of the Republic of Lysmark. Answers should be concise and human readable. AVOID references to tools or function calling nor show any JSON. Infer parameters for function calls or instead use default values or request the needed information from the user. Call the RAG tool first if unsure. Parameter single_parent_family only is necessary if birth/adoption/foster_care otherwise use false.
```

**Test queries:**
- "My mother had an accident and she's at the hospital. I have to take care of her, can I get access to the unpaid leave aid?"
- "I have just adopted two children, at the same time, aged 3 and 5, am I eligible for the unpaid leave aid? How much?"
- "I'm a single mom and I just had a baby, may I get access to the unpaid leave aid?"
- "Enumerate the legal requirements to get the aid for unpaid leave."

**Benefit cases:**

| Case | Situation | Benefit |
|------|-----------|---------|
| A | Illness/accident (first-degree family) | 725€/month |
| B | Third child or more (2+ under 6) | 500€/month |
| C | Adoption or foster care (>1 year) | 500€/month |
| D | Multiple birth/adoption | 500€/month |
| E | Single-parent family with newborn | 500€/month |
| NONE | Requirements not met | 0€ |

---

## Uninstall

```bash
helm uninstall llama-stack-demo --namespace ${PROJECT}
oc delete jobs -l "app.kubernetes.io/part-of=llama-stack-demo" -n ${PROJECT}
oc delete project ${PROJECT}
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Pods pending on GPU node | `oc describe node <gpu-node>` — verify `group: llama-stack-demo-userN` label |
| Pipeline hooks failing | `oc get svc minio -n minio` — Minio must be running |
| LlamaStack pod not starting | `oc logs llama-stack-demo-0 -n ${PROJECT}` |
| Model not loading | `oc logs qwen3-8b-fp8-dynamic-predictor-xxx -n ${PROJECT} -c kserve-container` |
| Monitoring missing | `./scripts/check-monitoring-telemetry.sh` |
| `no matches for kind "GrafanaDashboard"` on install | Grafana dashboards are opt-in and need the community Grafana Operator. Either omit `--set monitoring.enable=true` (default off), or install the Grafana Operator first. |
| Route timeout on first query | Normal — model loads on first request; HAProxy timeout is set to `1m` |
