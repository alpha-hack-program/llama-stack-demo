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
    
    # Configurar razonamiento
    reasoning = {
        "effort": "medium",  # 'low', 'medium', o 'high'
        "summary": "auto",   # 'detailed', 'auto', o None
    }

    # Create and return ChatOpenAI client
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=openai_endpoint,
        temperature=0.0,
        reasoning=reasoning,
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


def list_tool_groups(client: LlamaStackClient) -> List:
    """
    List all available tool groups from LlamaStack.
    
    Args:
        client: The LlamaStack client
    
    Returns:
        List of ToolGroup objects
        
    Raises:
        Exception: If there's an error fetching tool groups
    """
    return list(client.toolgroups.list())


def get_mcp_server_url(tool_group) -> Optional[str]:
    """
    Extract MCP server URL from a tool group object.
    
    This function checks multiple possible locations for the server URL:
    - mcp_endpoint.uri attribute
    - mcp_endpoint dict with 'uri' key
    - mcp_endpoint as a string
    - provider_resource_url attribute
    - metadata dict with 'url' or 'mcp_endpoint' keys
    
    Args:
        tool_group: A tool group object from LlamaStack
    
    Returns:
        Server URL string if found, None otherwise
    """
    # Check mcp_endpoint attribute
    if hasattr(tool_group, 'mcp_endpoint'):
        mcp_endpoint = tool_group.mcp_endpoint
        
        # Try to get URI from mcp_endpoint object
        if hasattr(mcp_endpoint, 'uri'):
            return mcp_endpoint.uri
        
        # Try mcp_endpoint as a dict
        if isinstance(mcp_endpoint, dict) and 'uri' in mcp_endpoint:
            return mcp_endpoint['uri']
        
        # Try mcp_endpoint as a string
        if isinstance(mcp_endpoint, str):
            return mcp_endpoint
    
    # Check provider_resource_url attribute
    if hasattr(tool_group, 'provider_resource_url'):
        return tool_group.provider_resource_url
    
    # Check metadata dict
    if hasattr(tool_group, 'metadata') and isinstance(tool_group.metadata, dict):
        return tool_group.metadata.get('url') or tool_group.metadata.get('mcp_endpoint')
    
    return None


def discover_tools(
    client: LlamaStackClient,
    vector_store_name: Optional[str] = None,
    include_web_search: bool = True,
    include_file_search: bool = True,
    include_mcp: bool = True
) -> List[dict]:
    """
    Auto-discover available tools from LlamaStack server.
    
    This function discovers and configures tools based on available tool groups:
    - Web search tools (builtin::websearch)
    - File search/RAG tools (builtin::rag) - requires vector_store_name
    - MCP server tools (mcp::*)
    
    Args:
        client: The LlamaStack client
        vector_store_name: Name of vector store for file_search tools (optional)
        include_web_search: Include web search tools if available (default: True)
        include_file_search: Include file search tools if available (default: True)
        include_mcp: Include MCP server tools if available (default: True)
    
    Returns:
        List of tool configuration dicts ready for LlamaStack API
        
    Example:
        tools = discover_tools(client, vector_store_name="my-store")
        # Returns:
        # [
        #     {"type": "web_search"},
        #     {"type": "file_search", "vector_store_ids": ["vs_123"]},
        #     {"type": "mcp", "server_label": "my-server", "server_url": "https://..."}
        # ]
    """
    from vector_stores import list_vector_stores
    
    tools = []
    skipped = []
    
    # Get vector store ID if needed for file_search
    vector_store_id = None
    if include_file_search and vector_store_name:
        try:
            vector_stores = list_vector_stores(client, vector_store_name)
            if vector_stores:
                vector_store_id = vector_stores[0].identifier
        except Exception:
            pass
    
    # Fetch tool groups
    try:
        tool_groups = list_tool_groups(client)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch tool groups: {e}")
    
    # Process each tool group
    for group in tool_groups:
        if not hasattr(group, 'identifier'):
            continue
        
        identifier = group.identifier
        
        # Web search tools
        if include_web_search and (identifier.startswith('builtin::websearch') or identifier.startswith('builtin::web_search')):
            tools.append({"type": "web_search"})
        
        # File search / RAG tools
        elif include_file_search and (identifier.startswith('builtin::rag') or identifier.startswith('builtin::file_search')):
            if vector_store_id:
                tools.append({
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id]
                })
            else:
                skipped.append(f"{identifier} (no vector store)")
        
        # MCP server tools
        elif include_mcp and identifier.startswith('mcp::'):
            server_url = get_mcp_server_url(group)
            if server_url:
                server_name = identifier.split('::', 1)[1] if '::' in identifier else identifier
                tools.append({
                    "type": "mcp",
                    "server_label": server_name,
                    "server_url": server_url
                })
            else:
                skipped.append(f"{identifier} (no server URL)")
    
    return tools, skipped
