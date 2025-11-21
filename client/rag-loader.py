import argparse

import os

from pathlib import Path
import time

from typing import List
from llama_stack_client.types import VectorStoreSearchResponse
from llama_stack_client.types.file import File
from llama_stack_client.types.vector_store import VectorStore
from llama_stack_client.types.vector_store_search_params import RankingOptions
from typing_extensions import Literal

from llama_stack_client import LlamaStackClient
from llama_stack_client.types.model import Model


# EMBEDDING_MODEL = "granite-embedding-125m"
# EMBEDDING_DIMENSION = "768"
# EMBEDDING_MODEL_PROVIDER = "sentence-transformers"
# CHUNK_SIZE_IN_TOKENS = 512
# LLAMA_STACK_HOST = "localhost"
# LLAMA_STACK_PORT = "8080"
# LLAMA_STACK_SECURE = "False"
# DOCS_FOLDER = "./docs"

DEFAULT_DELAY_SECONDS = 5


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


def list_files_in_folder(
    folder_path: str, 
    file_extensions: List[str] = ['.txt', '.md']
) -> List[Path]:
    """List files in a local folder and return file paths"""
    file_paths: List[Path] = []
    folder: Path = Path(folder_path)
    
    if not folder.exists():
        print(f"Warning: Folder {folder_path} does not exist")
        return file_paths
    
    print(f"Listing files in: {folder_path}")
    
    for file_path in folder.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in file_extensions:
            print(f"Found file: {file_path.name}")
            file_paths.append(file_path)
            
    print(f"Successfully listed {len(file_paths)} files")
    return file_paths


def upload_files(
    client: LlamaStackClient, 
    files: List[Path], 
) -> List[File]:
    """
    Upload files into the vector database.
    Args:
        client: The LlamaStack client
        files: The list of files to upload
    Returns:
        The list of file IDs
    """
    if not files:
        print("No files to upload")
        return
    
    file_ids = [upload_file(client, file) for file in files]
    print(f"Uploaded {len(file_ids)} files")
    return file_ids


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

def list_vector_stores(
    client: LlamaStackClient,
) -> List[VectorStore]:
    """
    List all vector stores.
    Args:
        client: The LlamaStack client
    Returns:
        The list of vector stores
    """
    vector_stores = client.vector_stores.list()
    return vector_stores

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

def upload_file(
    client: LlamaStackClient,
    file: Path,
    purpose: Literal["assistants", "batch"] = "assistants",
) -> File:
    """
    Upload a file into the vector store.
    Args:
        client: The LlamaStack client
        file: The file to upload
        purpose: The purpose of the file
    Returns:
        The file object
    """
    if not file.exists():
        raise ValueError(f"File {file} does not exist")
    
    # For each file (FilePath) create a file object and upload it to the vector store
    file_response = client.files.create(
        file=file,
        purpose=purpose
    )
    return file_response

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

def main() -> None:
    """Main function to load documents and insert them into the vector database"""

    # Takes an optional argument which adds a delay if the task fails using argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=str, default="0", help="Delay in seconds before raising error on failure")
    args = parser.parse_args()
    
    # Convert delay to integer, handling string input gracefully
    try:
        delay_seconds = int(args.delay)
        if delay_seconds < 0:
            raise ValueError("Delay must be a positive integer")
    except (ValueError, TypeError) as e:
        print(f"Warning: Invalid delay value '{args.delay}', defaulting to 0 seconds. Error: {e}")
        delay_seconds = DEFAULT_DELAY_SECONDS
    
    print(f"Delaying for {delay_seconds} seconds if task fails")
    
    try:
        # Get embedding model id, dimension and provider
        embedding_model_id = os.environ.get("EMBEDDING_MODEL")
        if embedding_model_id is None:
            raise ValueError("EMBEDDING_MODEL environment variable must be set")
        embedding_model_dimension = os.environ.get("EMBEDDING_DIMENSION")
        if embedding_model_dimension is None:
            raise ValueError("EMBEDDING_DIMENSION environment variable must be set")
        embedding_model_provider = os.environ.get("EMBEDDING_MODEL_PROVIDER")
        if embedding_model_provider is None:
            raise ValueError("EMBEDDING_MODEL_PROVIDER environment variable must be set")

        # Get chunk size in tokens
        chunk_size_in_tokens = os.environ.get("CHUNK_SIZE_IN_TOKENS", "512")
        chunk_size_in_tokens = int(chunk_size_in_tokens)

        # Get LlamaStack host, port and secure
        host = os.environ.get("LLAMA_STACK_HOST")
        if not host:
            raise ValueError("LLAMA_STACK_HOST environment variable must be set")
        port = os.environ.get("LLAMA_STACK_PORT")
        if not port:
            raise ValueError("LLAMA_STACK_PORT environment variable must be set")
        secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
        
        # Get vector store name
        vector_store_name = os.environ.get("VECTOR_STORE_NAME", "rag-store")

        # Get ranker
        ranker = str(os.environ.get("RANKER", "default"))

        # Get score threshold
        score_threshold = float(os.environ.get("SCORE_THRESHOLD", "0.8"))

        # Get max num results
        max_num_results = int(os.environ.get("MAX_NUM_RESULTS", "10"))

        # Get test query
        test_query = str(os.environ.get("TEST_QUERY", "Tell me about taxes in Lysmark."))

        # Add this after line ~195 where you read the environment variables
        print(f"DEBUG - Environment variables:")
        print(f"  HOST: '{host}'")
        print(f"  PORT: '{port}' (type: {type(port)})")
        print(f"  SECURE: '{secure}'")
        print(f"  VECTOR_STORE_NAME: '{vector_store_name}'")
        print(f"  RANKER: '{ranker}'")
        print(f"  SCORE_THRESHOLD: '{score_threshold}'")
        print(f"  MAX_NUM_RESULTS: '{max_num_results}'")
        print(f"  TEST_QUERY: '{test_query}'")
        
        # Get documents folder
        docs_folder: str = os.environ.get("DOCS_FOLDER", "./docs")
        if not docs_folder:
            raise ValueError("DOCS_FOLDER environment variable must be set")

        # Initialize client
        client: LlamaStackClient = create_client(host=host, port=int(port), secure=secure)
        print(f"Connected to LlamaStack at {host}:{port}")
        
        # List vector stores
        vector_stores: List[VectorStore] = list_vector_stores(client)
        if not vector_stores:
            print("No vector stores found")
        for vector_store in vector_stores:
            print(f"Deleting vector store: {vector_store})")
            delete_vector_store(client, vector_store.id)
            print(f"Deleted vector store: {vector_store.id}")

        # Get embedding model
        embedding_model = get_embedding_model(client, embedding_model_id, embedding_model_provider)
        if not embedding_model:
            raise ValueError(f"Embedding model {embedding_model_id} not found for provider {embedding_model_provider}")
        print(f"Using embedding model: {embedding_model.identifier} (dimension: {embedding_model.metadata['embedding_dimension']})")

        # Load documents from folder
        files_paths: List[Path] = list_files_in_folder(docs_folder)
        
        # Upload files into the vector database
        files = upload_files(client, files_paths)
        if not files:
            raise ValueError("No files uploaded")

        # List models
        models: List[Model] = list_models(client)
        for model in models:
            print(f"Model: {model.identifier} (provider: {model.provider_id} type: {model.api_model_type})")

        # Create vector store
        vector_store: VectorStore = create_vector_store(client, vector_store_name, files)
        
        print(f"Files uploaded into the vector store {vector_store.name} (id: {vector_store.id})")

        # Search the vector store
        search_response: VectorStoreSearchResponse = search_vector_store(client, vector_store.id, test_query, max_num_results=max_num_results, ranker=ranker, score_threshold=score_threshold)
        print(f"Search response: {search_response}")
    except Exception as e:
        print(f"Error: {e}")
        if delay_seconds > 0:
            print(f"Delaying for {delay_seconds} seconds before raising error")
            time.sleep(delay_seconds)
        raise e

if __name__ == "__main__":
    main()