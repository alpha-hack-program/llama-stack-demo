"""
Utility functions for LlamaStack client operations.
"""

import os
from llama_stack_client import LlamaStackClient
from llama_stack_client.types.model import Model
from llama_stack_client.types import VectorStore, VectorStoreSearchResponse
from typing import List, Optional


def create_client(host: str, port: int, secure: bool = False) -> LlamaStackClient:
    """Initialize and return the LlamaStack client"""
    if secure:
        protocol: str = "https"
    else:
        protocol: str = "http"

    if not (1 <= port <= 65535):
        raise ValueError(f"Port number {port} is out of valid range (1-65535).")
    if not host:
        raise ValueError("Host must be specified and cannot be empty.")
    
    print(f"Creating LlamaStack client with base URL: {protocol}://{host}:{port}")
    return LlamaStackClient(base_url=f"{protocol}://{host}:{port}")


def list_models(
    client: LlamaStackClient,
) -> List[Model]:
    """List all models.
    Args:
        client: The LlamaStack client
    Returns:
        The list of models
    """
    models: List[Model] = client.models.list()
    return models


def get_embedding_model(
    client: LlamaStackClient,
    embedding_model_id: str,
    embedding_model_provider: str
) -> Model:
    """Fetch and return the embedding model by ID and provider"""
    if not embedding_model_id:
        raise ValueError("Embedding model ID is required")
    if not embedding_model_provider:
        raise ValueError("Embedding model provider is required")
    
    models = client.models.list()
    for model in models:
        if model.identifier == embedding_model_id and model.provider_id == embedding_model_provider and model.api_model_type == "embedding":
            return model
    
    raise ValueError(f"Embedding model {embedding_model_id} not found for provider {embedding_model_provider}")


def create_langchain_client(
    model_name: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    secure: Optional[bool] = None,
    api_key: Optional[str] = None
):
    """
    Create a LangChain ChatOpenAI client configured for Llama Stack.
    
    Args:
        model_name: The name of the model to use
        host: Llama Stack host (defaults to LLAMA_STACK_HOST env var or "localhost")
        port: Llama Stack port (defaults to LLAMA_STACK_PORT env var or 8080)
        secure: Use HTTPS if True (defaults to LLAMA_STACK_SECURE env var or False)
        api_key: API key for authentication (defaults to API_KEY env var or "fake")
    
    Returns:
        ChatOpenAI client configured for Llama Stack
        
    Raises:
        ImportError: If LangChain dependencies are not installed
        ValueError: If host/port validation fails
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise ImportError(
            f"LangChain dependencies not installed: {e}\n"
            "Please install with: pip install langchain>=1.0 langchain-openai>=0.3.32 "
            "langchain-core>=0.3.75 langchain-mcp-adapters>=0.1.0"
        )
    
    # Get connection parameters from arguments or environment
    if host is None:
        host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    if port is None:
        port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    if secure is None:
        secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    # Validate parameters (same as create_client)
    if not (1 <= port <= 65535):
        raise ValueError(f"Port number {port} is out of valid range (1-65535).")
    if not host:
        raise ValueError("Host must be specified and cannot be empty.")
    
    # Build protocol and base URL
    protocol = "https" if secure else "http"
    base_url = f"{protocol}://{host}:{port}"
    
    # Construct OpenAI endpoint: base_url + /v1/openai/v1
    openai_endpoint = f"{base_url}/v1/openai/v1"
    
    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.environ.get("API_KEY", "fake")
    
    print(f"Creating LangChain client with base URL: {openai_endpoint}")
    
    # Create and return ChatOpenAI client
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=openai_endpoint,
        temperature=0.0,
    )


def get_rag_context(
    client: LlamaStackClient,
    vector_store_name: str,
    query: str,
    max_results: int = 10,
    score_threshold: float = 0.8,
    ranker: str = "default"
) -> str:
    """
    Retrieve context from a vector store for RAG (Retrieval-Augmented Generation).
    
    Args:
        client: The LlamaStack client
        vector_store_name: Name of the vector store to search
        query: The search query
        max_results: Maximum number of results to return (default: 10)
        score_threshold: Minimum score threshold for results (default: 0.8)
        ranker: Ranker to use for scoring (default: "default")
    
    Returns:
        Concatenated context string from retrieved documents, or empty string if no results
        
    Raises:
        ValueError: If vector store is not found
    """
    from vector_stores import list_vector_stores, search_vector_store
    
    # Find the vector store
    vector_stores: List[VectorStore] = list_vector_stores(client, name=vector_store_name)
    if not vector_stores:
        raise ValueError(f"Vector store {vector_store_name} not found")
    
    vector_store_id = vector_stores[0].id
    print(f"Using vector store: {vector_store_id}")
    
    # Search the vector store
    search_response: VectorStoreSearchResponse = search_vector_store(
        client,
        vector_store_id=vector_store_id,
        query=query,
        max_num_results=max_results,
        ranker=ranker,
        score_threshold=score_threshold
    )
    
    # Build context string from results
    context = ""
    for data in search_response.data:
        for content in data.content:
            context += f"{content.text}\n"
        context += "\n"
    
    return context


def augment_instructions_with_context(system_instructions: str, context: str) -> str:
    """
    Augment system instructions with retrieved context for RAG.
    
    Args:
        system_instructions: Original system instructions
        context: Retrieved context from vector store
    
    Returns:
        Augmented system instructions with context
    """
    if not context:
        return system_instructions
    
    return f"""
{system_instructions}

Use the following context to answer the question. If the question is not related to the context, don't take it into account:

<context>
{context}
</context>
"""
