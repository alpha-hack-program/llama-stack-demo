"""
Tool command implementation for managing and listing tool groups and tools.

This module provides functionality to interact with LlamaStack tool groups and tools.
"""

import os
import sys
from typing import List, Optional, Any
from llama_stack_client import LlamaStackClient
from utils import create_client, list_tool_groups


def groups_command(verbose: bool = False) -> List[Any]:
    """
    List all available tool groups from LlamaStack.
    
    Args:
        verbose: If True, show detailed information about each tool group
    
    Returns:
        List of ToolGroup objects
    """
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    print(f"Connecting to LlamaStack at {host}:{port}")
    client: LlamaStackClient = create_client(host=host, port=port, secure=secure)
    
    # Fetch all tool groups
    print("Fetching tool groups...")
    try:
        tool_groups = list_tool_groups(client)
    except Exception as e:
        print(f"Error fetching tool groups: {e}")
        return []
    
    if not tool_groups:
        print("No tool groups found.")
        return []
    
    # Display results
    print(f"\nFound {len(tool_groups)} tool group(s):\n")
    print("=" * 80)
    
    for idx, group in enumerate(tool_groups, 1):
        if verbose:
            print(f"\nTool Group {idx}:")
            print(f"  Identifier: {group.identifier if hasattr(group, 'identifier') else 'N/A'}")
            
            # Show provider_id if available
            if hasattr(group, 'provider_id') and group.provider_id:
                print(f"  Provider:   {group.provider_id}")
            
            # Show tools count by fetching tools
            try:
                tools_response = client.tools.list(toolgroup_id=group.identifier)
                tools_count = len(list(tools_response)) if tools_response else 0
                print(f"  Tools:      {tools_count} tool(s)")
            except Exception:
                print(f"  Tools:      Unable to fetch")
            
            # Show metadata if available
            if hasattr(group, 'metadata') and group.metadata:
                print(f"  Metadata:")
                for key, value in group.metadata.items():
                    print(f"    {key}: {value}")
            
            # Show all other attributes
            print(f"  All Attributes:")
            for attr in dir(group):
                if not attr.startswith('_') and not callable(getattr(group, attr)):
                    value = getattr(group, attr)
                    if value is not None and attr not in ['identifier', 'provider_id', 'tools', 'metadata']:
                        print(f"    {attr}: {value}")
            
            print("-" * 80)
        else:
            # Compact format
            identifier = group.identifier if hasattr(group, 'identifier') else 'N/A'
            provider = f"({group.provider_id})" if hasattr(group, 'provider_id') and group.provider_id else ""
            
            # Fetch tool count
            try:
                tools_response = client.tools.list(toolgroup_id=identifier)
                tool_count = len(list(tools_response)) if tools_response else 0
            except Exception:
                tool_count = "?"
            
            print(f"{idx:3}. {identifier:40} {provider:20} {tool_count} tool(s)")
    
    print("=" * 80)
    
    if len(tool_groups) > 1 and not verbose:
        print("\nTip: Use --verbose flag for detailed information")
    
    return tool_groups


def list_tools_command(
    group_name: Optional[str] = None,
    all_groups: bool = False,
    verbose: bool = False
) -> None:
    """
    List tools from tool groups.
    
    Args:
        group_name: Specific tool group identifier to list tools from
        all_groups: If True, list tools from all tool groups
        verbose: If True, show detailed information about each tool
    """
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    print(f"Connecting to LlamaStack at {host}:{port}")
    client: LlamaStackClient = create_client(host=host, port=port, secure=secure)
    
    # Validate arguments
    if not all_groups and not group_name:
        print("Error: Either --all or --group <group_name> must be specified.")
        sys.exit(1)
    
    if all_groups and group_name:
        print("Warning: Both --all and --group specified. Using --all (ignoring --group).")
    
    # Fetch all tool groups
    print("Fetching tool groups...")
    try:
        tool_groups = list_tool_groups(client)
    except Exception as e:
        print(f"Error fetching tool groups: {e}")
        sys.exit(1)
    
    if not tool_groups:
        print("No tool groups found.")
        return
    
    # Filter tool groups if needed
    if all_groups:
        selected_groups = tool_groups
        print(f"Listing tools from all {len(tool_groups)} tool group(s)...")
    else:
        # Find the specific group
        selected_groups = [g for g in tool_groups if 
                          (hasattr(g, 'identifier') and g.identifier == group_name)]
        
        if not selected_groups:
            print(f"Error: Tool group '{group_name}' not found.")
            print(f"\nAvailable tool groups:")
            for g in tool_groups:
                if hasattr(g, 'identifier'):
                    print(f"  - {g.identifier}")
            sys.exit(1)
        
        print(f"Listing tools from group: {group_name}")
    
    # Display tools
    print("\n" + "=" * 80)
    total_tools = 0
    
    for group_idx, group in enumerate(selected_groups, 1):
        group_identifier = group.identifier if hasattr(group, 'identifier') else f"Group {group_idx}"
        
        # Get tools from this group using the tools API
        tools = []
        try:
            tools_response = client.tools.list(toolgroup_id=group_identifier)
            # Convert to list if it's a response object
            tools = list(tools_response) if tools_response else []
        except Exception as e:
            print(f"  Warning: Could not fetch tools for group {group_identifier}: {e}")
        
        if all_groups:
            print(f"\n{'─' * 80}")
            print(f"Tool Group: {group_identifier}")
            print(f"{'─' * 80}")
        
        if not tools:
            print("  No tools found in this group.")
            continue
        
        total_tools += len(tools)
        print(f"  Found {len(tools)} tool(s):\n")
        
        for tool_idx, tool in enumerate(tools, 1):
            if verbose:
                print(f"  Tool {tool_idx}:")
                
                # Show common attributes
                if hasattr(tool, 'name'):
                    print(f"    Name:        {tool.name}")
                if hasattr(tool, 'description'):
                    print(f"    Description: {tool.description}")
                if hasattr(tool, 'type'):
                    print(f"    Type:        {tool.type}")
                
                # Show parameters if available
                if hasattr(tool, 'parameters') and tool.parameters:
                    print(f"    Parameters:")
                    if isinstance(tool.parameters, dict):
                        for key, value in tool.parameters.items():
                            print(f"      {key}: {value}")
                    else:
                        print(f"      {tool.parameters}")
                
                # Show all other attributes
                for attr in dir(tool):
                    if not attr.startswith('_') and not callable(getattr(tool, attr)):
                        value = getattr(tool, attr)
                        if value is not None and attr not in ['name', 'description', 'type', 'parameters']:
                            print(f"    {attr}: {value}")
                
                print()
            else:
                # Compact format
                tool_name = tool.name if hasattr(tool, 'name') else f"Tool {tool_idx}"
                tool_type = f"[{tool.type}]" if hasattr(tool, 'type') and tool.type else ""
                tool_desc = tool.description if hasattr(tool, 'description') and tool.description else ""
                
                # Truncate description if too long
                if tool_desc and len(tool_desc) > 50:
                    tool_desc = tool_desc[:47] + "..."
                
                print(f"    {tool_idx:3}. {tool_type:15} {tool_name:30} {tool_desc}")
    
    print("=" * 80)
    print(f"\nTotal: {total_tools} tool(s) across {len(selected_groups)} group(s)")
    
    if not verbose:
        print("\nTip: Use --verbose flag for detailed tool information")


def main() -> None:
    """
    Main entry point for standalone execution.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Manage and list tool groups and tools in LlamaStack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all tool groups
  python tool_command.py groups
  
  # List tool groups with details
  python tool_command.py groups --verbose
  
  # List all tools from all groups
  python tool_command.py list --all
  
  # List tools from a specific group
  python tool_command.py list --group "my-tool-group"
  
  # List tools with detailed information
  python tool_command.py list --all --verbose
  python tool_command.py list --group "my-tool-group" --verbose
        """
    )
    
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")
    subparsers.required = True
    
    # Groups subcommand
    groups_parser = subparsers.add_parser(
        "groups",
        help="List all tool groups"
    )
    groups_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed information about each tool group"
    )
    
    # List subcommand
    list_parser = subparsers.add_parser(
        "list",
        help="List tools from tool groups"
    )
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="List tools from all tool groups"
    )
    list_parser.add_argument(
        "--group",
        type=str,
        default=None,
        help="List tools from a specific tool group (by identifier)"
    )
    list_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed information about each tool"
    )
    
    args = parser.parse_args()
    
    # Execute the appropriate subcommand
    try:
        if args.subcommand == "groups":
            groups_command(verbose=args.verbose)
        elif args.subcommand == "list":
            list_tools_command(
                group_name=args.group,
                all_groups=args.all,
                verbose=args.verbose
            )
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

