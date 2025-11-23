"""
Search command implementation for RAG operations.
"""

import os
import sys
from typing import Optional
from llama_stack_client.types import VectorStoreSearchResponse
from typing_extensions import List

from llama_stack_client.types.vector_store_search_response import Data
from utils import create_client
from vector_stores import search_vector_store, list_vector_stores


def search_command(
    query: str,
    vector_store_id: Optional[str] = None,
    max_results: int = 10,
    score_threshold: float = 0.8,
    ranker: str = "default"
) -> None:
    """
    Search the vector store for relevant documents.
    
    Args:
        query: The search query
        vector_store_id: ID of the vector store to search (if None, uses latest)
        max_results: Maximum number of results to return (default: 10)
        score_threshold: Minimum score threshold for results (default: 0.8)
        ranker: Ranker to use for scoring (default: "default")
    """
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    print(f"Connecting to LlamaStack at {host}:{port}")
    client = create_client(host=host, port=port, secure=secure)
    
    # If no vector_store_id provided, get the latest one
    if vector_store_id is None:
        vector_stores_response = list_vector_stores(client)
        # Convert paginated response to list
        vector_stores = list(vector_stores_response)
        if not vector_stores:
            print("Error: No vector stores found. Please run 'load' command first.")
            sys.exit(1)
        # Use the most recently created vector store
        vector_store_id = vector_stores[-1].id
        print(f"Using vector store: {vector_store_id}")
    
    # Perform search
    print(f"\nSearching for: '{query}'")
    print(f"Parameters: max_results={max_results}, score_threshold={score_threshold}, ranker={ranker}")
    print("-" * 80)
    
    search_response: VectorStoreSearchResponse = search_vector_store(
        client=client,
        vector_store_id=vector_store_id,
        query=query,
        max_num_results=max_results,
        ranker=ranker,
        score_threshold=score_threshold
    )
    
    # Display results
    # The response might have different attribute names depending on the API version
    # Try common attribute names: results, chunks, data
    results: List[Data] = search_response.data
    if not results:
        print("No results found.")
        return
    
    print(f"\nFound {len(results)} results:\n")
    for idx, result in enumerate(results, 1):
        print(f"Result {idx}:")
        print(f"  Score: {result.score:.4f}")
        print(f"  Content: {result.content[:200]}..." if len(result.content) > 200 else f"  Content: {result.content}")
        if hasattr(result, 'metadata') and result.metadata:
            print(f"  Metadata: {result.metadata}")
        print()

