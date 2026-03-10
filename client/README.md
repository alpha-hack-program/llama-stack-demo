# LlamaStack Demo Client

This directory contains the client components for the LlamaStack demo: a **Streamlit chat app** (`app.py`), a **REST API server** (`server.py`), and shared utilities. Both applications connect to a LlamaStack backend and use the portazgo Agent for RAG and tool-augmented conversations.

## Core Image

A **single container image** (the "core image") serves both the Streamlit app and the REST API. It is built from this directory using the `Containerfile` and is used by the Helm chart for deployments.

- **Build**: `./image.sh build` (from the `client/` directory)
- **Image**: `llama-stack-demo-core` (see `.env` or `pyproject.toml` for registry/tag)
- **Entry points**:
  - `./start-app.sh` → Streamlit chat UI (port 8501) + health server (port 8081)
  - `./start-api.sh` → REST API (port 8700)

The Helm chart (`helm/templates/playground.yaml`) uses `llamaStackDemoCoreImage` for both deployments:
- **`-app`** deployment: runs `start-app.sh` (Streamlit)
- **`-api`** deployment: runs `start-api.sh` (REST API)

---

## app.py — Streamlit Chat

A chatbot UI that uses `portazgo.Agent` to talk to LlamaStack. Configuration is driven by `LLAMA_STACK_HOST`, `LLAMA_STACK_PORT`, and `LLAMA_STACK_SECURE`.

**Features:**
- Agent types: `default` (Llama Stack Responses API), `lang_graph` (LangGraph)
- Patterns: `simple`, `plan_execute`
- Model selection, vector store selection, MCP tools
- Optional display of think tokens and tool/context debug info

**Health checks** run in a separate process (`health-server.py`) because Flask and Streamlit conflict when embedded together.

**Run locally:**
```sh
cd client
uv sync
source .venv/bin/activate
uv run streamlit run app.py
```

---

## server.py — REST API

A FastAPI server exposing LlamaStack operations over HTTP.

**Endpoints:**
- `GET /health` — Liveness probe
- `GET /ready` — Readiness probe (checks LlamaStack connectivity)
- `GET /models`, `GET /models/{id}` — List and get model details
- `GET /tools/groups`, `GET /tools` — List tool groups and tools
- `POST /context` — RAG context retrieval from vector stores
- `GET /agents/types` — List agent types
- `POST /agents/execute` — Execute an agent (default, lang_chain, lang_graph)

**Run locally:**
```sh
cd client
uv sync
source .venv/bin/activate
python server.py
# API: http://localhost:8700
# Swagger UI: http://localhost:8700/docs
```

---

## Running via the Core Image

**Streamlit app:**
```sh
./image.sh app
# App: http://localhost:8501
# Health: http://localhost:8081
```

**REST API:**
```sh
./image.sh api
# API: http://localhost:8000 (or SERVER_PORT)
# Docs: http://localhost:8000/docs
```

Requires `.env` or `.test.env` with at least `LLAMA_STACK_HOST`, `LLAMA_STACK_PORT`, `LLAMA_STACK_SECURE`.

---

## Environment Setup

Set project and variables before running:

```sh
export PROJECT=llama-stack-demo
oc new-project ${PROJECT}
oc label namespace ${PROJECT} modelmesh-enabled=false opendatahub.io/dashboard=true
export APPS_DOMAIN=$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')
```

```sh
export EMBEDDING_MODEL="sentence-transformers/nomic-ai/nomic-embed-text-v1.5"
export EMBEDDING_DIMENSION="768"
export EMBEDDING_MODEL_PROVIDER="sentence-transformers"
export VECTOR_STORE_NAME="rag-store"
export VECTOR_STORE_PROVIDER_ID="milvus"
export RANKER="default"
export SCORE_THRESHOLD="0.8"
export MAX_NUM_RESULTS="10"
export LLAMA_STACK_HOST="llama-stack-demo-route-${PROJECT}.${APPS_DOMAIN}"
export LLAMA_STACK_PORT="443"
export LLAMA_STACK_SECURE="True"
export LOG_LEVEL="DEBUG"
```

---

## Example: Execute Agent via REST API

```sh
SYSTEM_INSTRUCTIONS="You are a helpful AI assistant that uses tools to help citizens of the Republic of Lysmark. Answers should be concise and human readable. AVOID references to tools or function calling nor show any JSON."
MODEL_NAME="llama-3-1-8b-w4a16"
AGENT_TYPE="lang_chain"

curl -X 'POST' \
  'http://0.0.0.0:8700/agents/execute' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "agent_type": "'"${AGENT_TYPE}"'",
  "input_text": "Tell me how much taxes do I have to pay if my yearly income is 43245€",
  "model_name": "'"${MODEL_NAME}"'",
  "system_instructions": "'"${SYSTEM_INSTRUCTIONS}"'",
  "tools": [
      { 
        "type": "mcp",
        "server_label": "dmcp",
        "server_url": "https://compatibility-engine-llama-stack-demo.apps.ocp.sandbox3322.opentlc.com/sse",
        "transport": "sse",
        "require_approval": "never"
      }
  ]
}'
```
