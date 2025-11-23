#!/bin/bash

# Set environment variables
export EMBEDDING_MODEL="granite-embedding-125m"
export EMBEDDING_DIMENSION="768"
export EMBEDDING_MODEL_PROVIDER="sentence-transformers"
export VECTOR_STORE_NAME="rag-store"
export RANKER="default"
export SCORE_THRESHOLD="0.8"
export MAX_NUM_RESULTS="10"
export TEST_QUERY="Tell me about taxes in Lysmark."
export LLAMA_STACK_HOST="eligibility-lsd-route-llama-stack-demo.apps.ocp.sandbox3322.opentlc.com"
export LLAMA_STACK_PORT="443"
export LLAMA_STACK_SECURE="True"
export DOCS_FOLDER="./docs"
export CHUNK_SIZE_IN_TOKENS="256"

# Run the script
python run.py "$@"