"""
Vector store operations for LlamaStack.
"""

from typing import List
from typing_extensions import Optional

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import VectorStoreSearchResponse
from llama_stack_client.types.file import File
from llama_stack_client.types.vector_store import VectorStore
from llama_stack_client.types.vector_store_search_params import RankingOptions


def create_vector_store(
    client: LlamaStackClient,
    name: str,
    files: List[File],
    provider_id: str = "milvus",
    embedding_model_id: str = "granite-embedding-125m",
    embedding_dimension: int = 768,
) -> VectorStore:
    """Create a vector store.
    Args:
        client: The LlamaStack client
        name: The name of the vector store
        files: The list of files to upload
        provider_id: The ID of the provider
        embedding_model_id: The ID of the embedding model
        embedding_dimension: The dimension of the embedding model
    Returns:
        The vector store
    """
    if not name:
        raise ValueError("Name is required for vector store creation")
    if not files:
        raise ValueError("Files are required for vector store creation")

    file_ids = [file.id for file in files]
    vector_store = client.vector_stores.create(
        name=name,
        file_ids=file_ids,
        extra_body={
            "provider_id": provider_id,
            "embedding_model": embedding_model_id,
            "embedding_dimension": embedding_dimension,
        }
    )
    print(f"Created vector store: {name}")
    return vector_store


def list_vector_stores(
    client: LlamaStackClient,
    name: Optional[str] = None,
) -> List[VectorStore]:
    """
    List all vector stores.
    Args:
        client: The LlamaStack client
        name: The name of the vector store to list
    Returns:
        The list of vector stores
    """
    vector_stores: List[VectorStore] = list(client.vector_stores.list())    
    if name:
        vector_stores = [v for v in vector_stores if v.name == name]
    return vector_stores


def delete_vector_store(
    client: LlamaStackClient,
    vector_store_id: str,
) -> None:
    """
    Delete a vector store.
    Args:
        client: The LlamaStack client
        vector_store_id: The ID of the vector store to delete
    Returns:
        The ID of the deleted vector store
    """
    if not vector_store_id:
        raise ValueError("Vector store ID is required for vector store deletion")
    client.vector_stores.delete(vector_store_id=vector_store_id)
    print(f"Deleted vector store: {vector_store_id}")
    return vector_store_id


def search_vector_store(
    client: LlamaStackClient,
    vector_store_id: str,
    query: str,
    max_num_results: int = 10,
    ranker: str = "default",
    score_threshold: float = 0.8,
) -> VectorStoreSearchResponse:
    """
    Search a vector store.
    Args:
        client: The LlamaStack client
        vector_store_id: The ID of the vector store to search
        query: The query to search the vector store
        max_num_results: The maximum number of results to return
        ranker: The ranker to use
        score_threshold: The score threshold to use
    Returns:
        The search response
    """
    ranking_options = RankingOptions(
        ranker=ranker,
        score_threshold=score_threshold,
    )
    return client.vector_stores.search(vector_store_id=vector_store_id, query=query, ranking_options=ranking_options, max_num_results=max_num_results)

