"""
Model command implementation for managing and listing models.

This module provides functionality to interact with LlamaStack models.
"""

import os
import sys
from typing import List, Optional
from llama_stack_client import LlamaStackClient
from llama_stack_client.types.model import Model
from utils import create_client, list_models


def list_command(
    filter_provider: Optional[str] = None,
    filter_type: Optional[str] = None,
    verbose: bool = False
) -> List[Model]:
    """
    List all available models from LlamaStack.
    
    Args:
        filter_provider: Optional provider ID to filter by (e.g., 'meta', 'ollama')
        filter_type: Optional model type to filter by (e.g., 'llm', 'embedding')
        verbose: If True, show detailed information about each model
    
    Returns:
        List of Model objects
    """
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    print(f"Connecting to LlamaStack at {host}:{port}")
    client: LlamaStackClient = create_client(host=host, port=port, secure=secure)
    
    # Fetch all models
    print("Fetching models...")
    models: List[Model] = list_models(client)
    
    if not models:
        print("No models found.")
        return []
    
    # Apply filters if provided
    filtered_models = models
    if filter_provider:
        filtered_models = [m for m in filtered_models if m.provider_id == filter_provider]
        print(f"Filtered by provider: {filter_provider}")
    
    if filter_type:
        filtered_models = [m for m in filtered_models if m.api_model_type == filter_type]
        print(f"Filtered by type: {filter_type}")
    
    if not filtered_models:
        print(f"No models found matching the filters.")
        return []
    
    # Display results
    print(f"\nFound {len(filtered_models)} model(s):\n")
    print("=" * 80)
    
    for idx, model in enumerate(filtered_models, 1):
        if verbose:
            print(f"\nModel {idx}:")
            print(f"  Identifier:  {model.identifier}")
            print(f"  Provider:    {model.provider_id}")
            print(f"  Type:        {model.api_model_type}")
            
            # Show metadata if available
            if hasattr(model, 'metadata') and model.metadata:
                print(f"  Metadata:")
                for key, value in model.metadata.items():
                    print(f"    {key}: {value}")
            
            # Show provider resource ID if available
            if hasattr(model, 'provider_resource_id') and model.provider_resource_id:
                print(f"  Provider Resource ID: {model.provider_resource_id}")
            
            print("-" * 80)
        else:
            # Compact format
            type_str = f"[{model.api_model_type}]".ljust(12)
            provider_str = f"({model.provider_id})".ljust(20)
            print(f"{idx:3}. {type_str} {provider_str} {model.identifier}")
    
    print("=" * 80)
    
    # Summary by type and provider
    if len(filtered_models) > 1 and not verbose:
        print("\nSummary:")
        types = {}
        providers = {}
        for model in filtered_models:
            types[model.api_model_type] = types.get(model.api_model_type, 0) + 1
            providers[model.provider_id] = providers.get(model.provider_id, 0) + 1
        
        print(f"  By Type: {dict(types)}")
        print(f"  By Provider: {dict(providers)}")
        print("\nTip: Use --verbose flag for detailed information")
    
    return filtered_models


def info_command(model_identifier: str) -> None:
    """
    Show detailed information about a specific model.
    
    Args:
        model_identifier: The identifier of the model to get info about
    """
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    print(f"Connecting to LlamaStack at {host}:{port}")
    client: LlamaStackClient = create_client(host=host, port=port, secure=secure)
    
    # Fetch all models
    models: List[Model] = list_models(client)
    
    # Find the specific model
    model = next((m for m in models if m.identifier == model_identifier), None)
    
    if not model:
        print(f"Error: Model '{model_identifier}' not found.")
        print(f"\nAvailable models:")
        for m in models:
            print(f"  - {m.identifier}")
        sys.exit(1)
    
    # Display detailed information
    print("\n" + "=" * 80)
    print(f"MODEL INFORMATION: {model.identifier}")
    print("=" * 80)
    print(f"\nIdentifier:  {model.identifier}")
    print(f"Provider:    {model.provider_id}")
    print(f"Type:        {model.api_model_type}")
    
    if hasattr(model, 'provider_resource_id') and model.provider_resource_id:
        print(f"Provider Resource ID: {model.provider_resource_id}")
    
    if hasattr(model, 'metadata') and model.metadata:
        print(f"\nMetadata:")
        for key, value in model.metadata.items():
            print(f"  {key}: {value}")
    
    # Show all attributes
    print(f"\nAll Attributes:")
    for attr in dir(model):
        if not attr.startswith('_') and not callable(getattr(model, attr)):
            value = getattr(model, attr)
            if value is not None and attr not in ['identifier', 'provider_id', 'api_model_type', 'metadata', 'provider_resource_id']:
                print(f"  {attr}: {value}")
    
    print("=" * 80)


def main() -> None:
    """
    Main entry point for standalone execution.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Manage and list LlamaStack models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all models
  python model_command.py list
  
  # List models with detailed information
  python model_command.py list --verbose
  
  # Filter by provider
  python model_command.py list --provider meta
  
  # Filter by type
  python model_command.py list --type embedding
  
  # Get info about a specific model
  python model_command.py info --model "meta-llama/Llama-3.2-3B-Instruct"
        """
    )
    
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")
    subparsers.required = True
    
    # List subcommand
    list_parser = subparsers.add_parser(
        "list",
        help="List all available models"
    )
    list_parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Filter by provider ID (e.g., 'meta', 'ollama')"
    )
    list_parser.add_argument(
        "--type",
        type=str,
        default=None,
        help="Filter by model type (e.g., 'llm', 'embedding')"
    )
    list_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed information about each model"
    )
    
    # Info subcommand
    info_parser = subparsers.add_parser(
        "info",
        help="Show detailed information about a specific model"
    )
    info_parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model identifier to get information about"
    )
    
    args = parser.parse_args()
    
    # Execute the appropriate subcommand
    try:
        if args.subcommand == "list":
            list_command(
                filter_provider=args.provider,
                filter_type=args.type,
                verbose=args.verbose
            )
        elif args.subcommand == "info":
            info_command(model_identifier=args.model)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

