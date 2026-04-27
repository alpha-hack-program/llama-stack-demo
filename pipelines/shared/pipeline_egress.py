# SPDX-License-Identifier: Apache-2.0
"""
Map cluster ConfigMap `rag-pipeline-config` into KFP task env (Llama Stack, HTTP(S)
proxy, PyPI / pip). Must stay aligned with the first ConfigMap in helm/templates/hooks.yaml.

`compile_and_upsert` runs in the Helm hook pod; that job sets the same values as the
ConfigMap, so the compiled IR only requests ConfigMap keys that exist at run time.
"""

import os
from kfp import kubernetes

RAG_PIPELINE_CONFIG_NAME = "rag-pipeline-config"

_BASE = {
    "LLAMA_STACK_HOST": "LLAMA_STACK_HOST",
    "LLAMA_STACK_PORT": "LLAMA_STACK_PORT",
    "LLAMA_STACK_SECURE": "LLAMA_STACK_SECURE",
}

# Optional: only if set in the compile environment (keep in sync with ConfigMap/values)
_OPTIONAL = (
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "NO_PROXY",
    "no_proxy",
    "PIP_INDEX_URL",
    "PIP_EXTRA_INDEX_URL",
    "PIP_TRUSTED_HOST",
)


def build_rag_configmap_key_to_env():
    m = dict(_BASE)
    for k in _OPTIONAL:
        if (os.environ.get(k) or "").strip():
            m[k] = k
    return m


def apply_rag_configmap_as_env(task) -> None:
    kubernetes.use_config_map_as_env(
        task=task,
        config_map_name=RAG_PIPELINE_CONFIG_NAME,
        config_map_key_to_env=build_rag_configmap_key_to_env(),
    )
