"""
Agent command implementation for running different types of agents.

This module provides agent functionality using LlamaStack with support for:
- Default agent: Uses MCP servers for tool calling
- LangChain agent: Alternative agent implementation using LangChain 1.0
- LangGraph agent: ReAct agent using LangGraph with OpenAI native MCP support
"""

import os
import sys
from typing import List, Dict, Any, Optional, Generator, Tuple, Callable
from llama_stack_client import LlamaStackClient
from llama_stack_client.types import ResponseObject, VectorStore, VectorStoreSearchResponse
from vector_stores import list_vector_stores, search_vector_store
from utils import (
    create_client, 
    create_langchain_client, 
    get_rag_context, 
    augment_instructions_with_context,
    discover_tools,
    list_tool_groups,
    get_mcp_server_url
)
from streaming_logger import StreamingLogHandler
from agent_events import AgentEventHandler, LangChainAgentCallback


def default_agent(
    input_text: str,
    model_name: str,
    system_instructions: str,
    vector_store_name: Optional[str] = None,
    max_results: int = 10,
    score_threshold: float = 0.8,
    ranker: str = "default",
    tools: Optional[List[Dict[str, Any]]] = None,
    event_handler: Optional[AgentEventHandler] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Execute the default agent using LlamaStack with native MCP server support.
    
    This implementation uses Llama Stack's native MCP integration where the server
    handles tool discovery and execution directly.
    
    **Architecture**:
    - Native Llama Stack Responses API
    - Server-side MCP tool calling
    - Direct integration with MCP servers
    
    Args:
        input_text: The input prompt for the agent
        model_name: The name of the model to use
        system_instructions: System instructions for the agent
        vector_store_name: Name of vector store for RAG (optional)
        max_results: Maximum number of RAG results (default: 10)
        score_threshold: Minimum score threshold for RAG results (default: 0.8)
        ranker: Ranker to use for RAG scoring (default: "default")
        tools: List of tools/MCP servers to use (optional, defaults to configured servers)
        event_handler: Optional AgentEventHandler for structured event tracking
    
    Returns:
        Tuple of (response_text, structured_data_dict)
    """
    # Create event handler if not provided
    if event_handler is None:
        event_handler = AgentEventHandler()
    
    print("\n" + "=" * 80)
    print("🚀 Executing Default Agent with Llama Stack")
    print("=" * 80)
    print(f"\n📥 User Query: {input_text}")
    print(f"🤖 Model: {model_name}")
    print("-" * 80)
    
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    print(f"\n🔗 Connecting to Llama Stack at {host}:{port}")
    client: LlamaStackClient = create_client(host=host, port=port, secure=secure)
    print(f"   ✅ Connected successfully!")
    
    # Handle RAG if vector store is specified
    if vector_store_name:
        print(f"\n🔍 RAG: Searching vector store '{vector_store_name}'...")
        
        try:
            context = get_rag_context(
                client=client,
                vector_store_name=vector_store_name,
                query=input_text,
                max_results=max_results,
                score_threshold=score_threshold,
                ranker=ranker
            )
            
            # Augment system instructions with context
            if context:
                system_instructions = augment_instructions_with_context(system_instructions, context)
                print(f"   ✅ System instructions augmented with RAG context")
        except ValueError as e:
            print(f"   ⚠️  {e}. Continuing without RAG.")
    else:
        print("\nℹ️  No vector store specified, proceeding without RAG")

    # Use provided tools or auto-discover from server
    if tools is None:
        # Auto-discover tool groups from the server
        print("\n🔍 Auto-discovering available tool groups...")
        try:
            tools, skipped = discover_tools(
                client=client,
                vector_store_name=vector_store_name,
                include_web_search=True,
                include_file_search=True,
                include_mcp=True
            )
            
            if tools:
                tool_names = []
                for t in tools:
                    if t['type'] == 'mcp':
                        tool_names.append(f"{t['type']}::{t.get('server_label', 'unknown')}")
                    elif t['type'] == 'file_search':
                        tool_names.append(f"{t['type']}::rag")
                    else:
                        tool_names.append(t['type'])
                print(f"   ✅ Configured {len(tools)} tool(s): {tool_names}")
                
                if skipped:
                    for skip_msg in skipped:
                        print(f"   ⚠️  Skipping {skip_msg}")
            else:
                print("   ℹ️  No compatible tool groups found")
        except Exception as e:
            tools = []
            print(f"   ⚠️  Could not fetch tool groups: {e}")
            print("   Agent will work without external tool access")
    elif len(tools) == 0:
        print("\n⚠️  No tools configured (--no-tools flag used)")
        print("   Agent will work without external tool access")
    
    # Display tool configuration
    if len(tools) > 0:
        print("\n🛠️  Configuring tools (server-side execution)...")
        for tool_config in tools:
            tool_type = tool_config.get("type", "unknown")
            if tool_type == "mcp":
                server_label = tool_config.get("server_label", "Unknown")
                server_url = tool_config.get("server_url", "N/A")
                print(f"   - MCP Server: {server_label} ({server_url})")
            elif tool_type in ["web_search", "websearch"]:
                print(f"   - Web Search")
            elif tool_type == "file_search":
                vector_store_ids = tool_config.get("vector_store_ids", [])
                stores_str = ", ".join(vector_store_ids) if vector_store_ids else "N/A"
                print(f"   - File Search (RAG): {stores_str}")
            elif tool_type == "function":
                func_name = tool_config.get("name", tool_config.get("function_name", "Unknown"))
                print(f"   - Function: {func_name}")
            else:
                print(f"   - Tool ({tool_type}): {tool_config}")
        print(f"   ℹ️  Llama Stack will handle tool discovery and execution")
    
    # Prepare configuration for Llama Stack
    config = {
        "input": input_text,
        "model": model_name,
        "instructions": system_instructions,
        "tools": tools
    }
    
    # Execute the agent
    print("\n" + "=" * 80)
    print("🔄 Executing Agent...")
    print("=" * 80 + "\n")
    
    response: ResponseObject = client.responses.create(**config)

    # Display response details and emit structured events
    print("\n📊 Agent Response:")
    print("-" * 80)
    
    # Try to extract and display tool execution details
    import json
    
    # Check for tool execution in different possible attributes
    if hasattr(response, 'turns') and response.turns:
        print(f"\n🔄 Agent Turns: {len(response.turns)}")
        for i, turn in enumerate(response.turns):
            print(f"\n━━ Turn {i+1} ━━")
            
            # Check for tool calls in the turn
            if hasattr(turn, 'tool_calls') and turn.tool_calls:
                for tool_call in turn.tool_calls:
                    tool_name = tool_call.tool_name if hasattr(tool_call, 'tool_name') else 'Unknown'
                    tool_args = tool_call.arguments if hasattr(tool_call, 'arguments') else {}
                    tool_result = tool_call.response if hasattr(tool_call, 'response') else None
                    
                    # Emit on_tool_start event
                    event_handler.on_tool_start(
                        {"name": tool_name},
                        str(tool_args)
                    )
                    
                    print(f"\n🔧 Tool Called: {tool_name}")
                    if tool_args:
                        try:
                            args_formatted = json.dumps(tool_args, indent=2)
                            print(f"📝 Arguments:\n{args_formatted}")
                        except:
                            print(f"📝 Arguments: {tool_args}")
                    
                    # Emit on_tool_end event
                    if tool_result:
                        event_handler.on_tool_end(str(tool_result))
                        try:
                            response_formatted = json.dumps(tool_result, indent=2)
                            print(f"🛠️  Result:\n{response_formatted}")
                        except:
                            print(f"🛠️  Result: {tool_result}")
            
            # Check for step execution details
            if hasattr(turn, 'steps') and turn.steps:
                for step in turn.steps:
                    if hasattr(step, 'tool_name'):
                        tool_name = step.tool_name
                        tool_args = step.tool_args if hasattr(step, 'tool_args') else {}
                        tool_result = step.tool_response if hasattr(step, 'tool_response') else None
                        
                        # Emit on_tool_start event
                        event_handler.on_tool_start(
                            {"name": tool_name},
                            str(tool_args)
                        )
                        
                        print(f"\n🔧 Tool: {tool_name}")
                        if tool_args:
                            try:
                                args_formatted = json.dumps(tool_args, indent=2)
                                print(f"📝 Arguments:\n{args_formatted}")
                            except:
                                print(f"📝 Arguments: {tool_args}")
                        
                        # Emit on_tool_end event
                        if tool_result:
                            event_handler.on_tool_end(str(tool_result))
                            try:
                                resp_formatted = json.dumps(tool_result, indent=2)
                                print(f"🛠️  Result:\n{resp_formatted}")
                            except:
                                print(f"🛠️  Result: {tool_result}")
    
    # Legacy check for direct tool_calls attribute
    elif hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"\n🛠️  Tools Used: {len(response.tool_calls)}")
        for tool_call in response.tool_calls:
            # Try to extract more details if available
            tool_name = "unknown"
            tool_args = {}
            tool_result = None
            
            if hasattr(tool_call, '__dict__'):
                tool_dict = tool_call.__dict__
                tool_name = tool_dict.get('tool_name', 'unknown')
                tool_args = tool_dict.get('arguments', {})
                tool_result = tool_dict.get('response', None)
                
                # Emit events
                event_handler.on_tool_start({"name": tool_name}, str(tool_args))
                if tool_result:
                    event_handler.on_tool_end(str(tool_result))
                
                print(f"\n🔧 Tool: {tool_name}")
                try:
                    print(f"📋 Details:\n{json.dumps(tool_dict, indent=2, default=str)}")
                except:
                    print(f"📋 Details: {tool_dict}")
    
    # If no tool execution info found, check raw response structure
    elif os.environ.get("DEBUG_RESPONSE", "false").lower() == "true":
        print(f"\n🔍 Response Structure (DEBUG):")
        print(f"   Type: {type(response)}")
        print(f"   Attributes: {dir(response)}")
        if hasattr(response, '__dict__'):
            print(f"   Data: {json.dumps(response.__dict__, indent=2, default=str)}")
    
    print(f"\n🤖 Final Answer: {response.output_text}")
    
    print("\n" + "=" * 80)
    print("✅ Default Agent Execution Complete!")
    print("=" * 80)
    
    # Return response and structured data (matching LangChain/LangGraph format)
    return response.output_text, {
        "events": event_handler.get_events(),
        "tool_calls": event_handler.get_tool_calls(),
        "final_response": response.output_text
    }


async def langchain_agent(
    input_text: str,
    model_name: str,
    system_instructions: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    vector_store_name: Optional[str] = None,
    max_results: int = 10,
    score_threshold: float = 0.8,
    ranker: str = "default",
    event_handler: Optional[AgentEventHandler] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Execute the LangChain agent implementation using LangChain 1.0 with MCP adapters.
    
    This implementation connects to Llama Stack's OpenAI-compatible endpoint and uses
    MCP (Model Context Protocol) adapters for client-side tool execution.
    
    Architecture:
    - LangChain 1.0 Agent (create_agent)
    - Llama Stack (OpenAI API via vLLM engine)
    - MCP Client (langchain-mcp-adapters with SSE transport)
    - MCP Servers (tool execution)
    
    Args:
        input_text: The input prompt for the agent
        model_name: The name of the model to use
        system_instructions: System instructions for the agent
        tools: List of MCP server configs (optional, defaults to configured servers)
        vector_store_name: Name of vector store for RAG (optional)
        max_results: Maximum number of RAG results (default: 10)
        score_threshold: Minimum score threshold for RAG results (default: 0.8)
        ranker: Ranker to use for RAG scoring (default: "default")
        event_handler: Optional AgentEventHandler for structured event tracking
    
    Returns:
        Tuple of (response_text, structured_data_dict)
    """
    try:
        from langchain.agents import create_agent
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    except ImportError as e:
        raise ImportError(
            f"LangChain dependencies not installed: {e}\n"
            "Please install with: pip install langchain>=1.0 langchain-openai>=0.3.32 "
            "langchain-core>=0.3.75 langchain-mcp-adapters>=0.1.0"
        )
    
    print("\n" + "=" * 80)
    print("🚀 Executing LangChain 1.0 Agent with MCP Tools")
    print("=" * 80)
    print(f"\n📥 User Query: {input_text}")
    print(f"🤖 Model: {model_name}")
    print("-" * 80)
    
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    # Create LangChain client for Llama Stack
    llm = create_langchain_client(
        model_name=model_name,
        host=host,
        port=port,
        secure=secure
    )
    
    # Test connectivity
    print("\n🧪 Testing Llama Stack connectivity...")
    try:
        test_response = llm.invoke("Say 'Connection successful' if you can read this.")
        print(f"   ✅ Connection successful!")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Llama Stack: {e}")
    
    # Handle RAG if vector store is specified
    if vector_store_name:
        print(f"\n🔍 RAG: Searching vector store '{vector_store_name}'...")
        
        client = create_client(host=host, port=port, secure=secure)
        
        try:
            context = get_rag_context(
                client=client,
                vector_store_name=vector_store_name,
                query=input_text,
                max_results=max_results,
                score_threshold=score_threshold,
                ranker=ranker
            )
            
            # Augment system instructions with context
            if context:
                system_instructions = augment_instructions_with_context(system_instructions, context)
                print(f"   ✅ System instructions augmented with RAG context")
        except ValueError as e:
            print(f"   ⚠️  {e}. Continuing without RAG.")
    else:
        print("\nNo vector store name provided, using default tools without vector store search")
    
    # Use provided tools or auto-discover from server
    if tools is None:
        # Auto-discover tool groups from the server (only MCP servers for LangChain)
        print("\n🔍 Auto-discovering available MCP servers...")
        try:
            client = create_client(host=host, port=port, secure=secure)
            tools, skipped = discover_tools(
                client=client,
                vector_store_name=None,  # LangChain doesn't use file_search
                include_web_search=False,  # LangChain doesn't use web_search
                include_file_search=False,  # LangChain doesn't use file_search
                include_mcp=True  # Only MCP servers
            )
            
            if tools:
                print(f"   ✅ Found {len(tools)} MCP server(s): {[t['server_label'] for t in tools]}")
                if skipped:
                    for skip_msg in skipped:
                        print(f"   ⚠️  Skipping {skip_msg}")
            else:
                print("   ℹ️  No MCP servers found")
        except Exception as e:
            tools = []
            print(f"   ⚠️  Could not fetch tool groups: {e}")
            print("   Agent will work without external tool access")
    elif len(tools) == 0:
        print("\n⚠️  No tools configured (--no-tools flag used)")
        print("   Agent will work without external tool access")
    
    # Build MCP client configuration
    mcp_config = {}
    if len(tools) > 0:
        print("\n🛠️  Configuring MCP client...")
        for tool_config in tools:
            if tool_config.get("type") == "mcp":
                server_label = tool_config.get("server_label", "Unknown")
                server_url = tool_config.get("server_url", "Unknown")
                mcp_config[server_label] = {
                    "transport": "sse",
                    "url": server_url,
                }
                print(f"   - MCP Server: {server_label}: {server_url}")
            elif tool_config.get("type") == "toolgroup":
                print(f"   ⚠️  Warning: Tool groups are not supported in LangChain agent mode")
                print(f"      Tool group '{tool_config.get('toolgroup_id')}' will be ignored")
                print(f"      Please use 'default' agent type for tool group support")
    
    # Create MCP client and get tools with error handling
    print("\n📦 Loading MCP tools...")
    langchain_tools = []
    
    if mcp_config:
        try:
            import asyncio
            
            mcp_client = MultiServerMCPClient(mcp_config)
            
            # Add timeout for port-forwarding scenarios (kubefwd/kubectl)
            try:
                langchain_tools = await asyncio.wait_for(
                    mcp_client.get_tools(),
                    timeout=30.0  # 30 second timeout for SSE connection
                )
            except asyncio.TimeoutError:
                print(f"   ⚠️  Warning: Timeout loading MCP tools (30s)")
                print(f"   💡 SSE connections through port forwarding can timeout")
                print(f"   💡 Tip: Use 'kubectl port-forward' instead of kubefwd for better SSE support")
                raise
            
            print(f"   ✅ Loaded {len(langchain_tools)} tools from MCP servers:")
            for tool in langchain_tools:
                print(f"      - {tool.name}: {tool.description}")
        except Exception as e:
            import traceback
            print(f"   ⚠️  Warning: Failed to load MCP tools: {e}")
            print(f"   🔍 Error type: {type(e).__name__}")
            
            # Show detailed trace for debugging
            if os.environ.get("DEBUG_MCP", "false").lower() == "true":
                print(f"   🔍 Full traceback:")
                print(traceback.format_exc())
            
            print(f"   ⚠️  Continuing without MCP tools. The agent will work without external tool access.")
            print(f"   💡 Tip: Check if MCP servers are running and accessible:")
            for server_label, config in mcp_config.items():
                print(f"      - {server_label}: {config['url']}")
            print(f"   💡 If using kubefwd: SSE may not work, try 'kubectl port-forward' instead")
    else:
        print("   ℹ️  No MCP servers configured, continuing without tools")
    
    # Create event handler if not provided
    if event_handler is None:
        event_handler = LangChainAgentCallback()
    
    # Create LangChain agent using create_agent API
    print("\n🤖 Creating LangChain agent...")
    
    if langchain_tools:
        agent = create_agent(
            model=llm,
            tools=langchain_tools,
            system_prompt=system_instructions,
        )
        print(f"   ✅ Agent created successfully with {len(langchain_tools)} tools!")
    else:
        agent = create_agent(
            model=llm,
            tools=[],  # Empty tools list
            system_prompt=system_instructions,
        )
        print(f"   ✅ Agent created successfully (without tools)")
        print(f"   ℹ️  Note: Agent will answer based on model knowledge only")
    
    # Execute the agent
    print("\n" + "=" * 80)
    print("🔄 Executing Agent...")
    print("=" * 80 + "\n")
    
    # Execute with callbacks to capture structured events
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": input_text}]},
        config={"callbacks": [event_handler]}
    )
    
    # Display execution trace
    print("\n📊 Agent Execution Trace:")
    print("-" * 80)
    
    final_response = ""
    for message in result["messages"]:
        if isinstance(message, HumanMessage):
            print(f"\n👤 Human: {message.content}")
        
        elif isinstance(message, AIMessage):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                print(f"\n🤖 AI (Tool Call):")
                for tool_call in message.tool_calls:
                    print(f"   🔧 Tool: {tool_call['name']}")
                    # Print args as formatted JSON
                    import json
                    try:
                        args_json = json.dumps(tool_call['args'], indent=2)
                        print(f"   📝 Args: {args_json}")
                    except:
                        print(f"   📝 Args: {tool_call['args']}")
            else:
                print(f"\n🤖 AI: {message.content}")
                final_response = message.content
        
        elif isinstance(message, ToolMessage):
            # Show full content, no truncation
            import json
            content_str = str(message.content)
            # Try to pretty-print if it's JSON
            try:
                content_obj = json.loads(content_str)
                content_formatted = json.dumps(content_obj, indent=2)
                print(f"\n🛠️  Tool Result:\n{content_formatted}")
            except:
                # Not JSON, just print as-is
                print(f"\n🛠️  Tool Result: {content_str}")
    
    print("\n" + "=" * 80)
    print("✅ LangChain Agent Execution Complete!")
    print("=" * 80)
    
    # Return response and structured data
    return final_response, {
        "events": event_handler.get_events(),
        "tool_calls": event_handler.get_tool_calls(),
        "final_response": final_response
    }

async def langgraph_agent(
    input_text: str,
    model_name: str,
    system_instructions: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    vector_store_name: Optional[str] = None,
    max_results: int = 10,
    score_threshold: float = 0.8,
    ranker: str = "default",
    event_handler: Optional[AgentEventHandler] = None,
    use_streaming: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Execute the LangGraph agent implementation using LangChain with Llama Stack.
    
    This implementation uses Llama Stack's OpenAI-compatible endpoint and MCP adapters
    for client-side tool execution, similar to the LangChain agent.
    
    **Architecture**:
    - LangGraph ReAct Agent (create_agent from langchain.agents)
    - Llama Stack (OpenAI-compatible API via vLLM engine)
    - MCP Client (langchain-mcp-adapters with SSE transport)
    - MCP Servers (tool execution)
    
    Args:
        input_text: The input prompt for the agent
        model_name: The name of the model to use (from Llama Stack)
        system_instructions: System instructions for the agent
        tools: List of MCP server configs (optional, defaults to configured servers)
        vector_store_name: Name of vector store for RAG (optional)
        max_results: Maximum number of RAG results (default: 10)
        score_threshold: Minimum score threshold for RAG results (default: 0.8)
        ranker: Ranker to use for RAG scoring (default: "default")
        event_handler: Optional AgentEventHandler for structured event tracking
        use_streaming: Whether to use astream_events for real-time event capture (default: True)
    
    Returns:
        Tuple of (response_text, structured_data_dict)
    """
    try:
        from langchain.agents import create_agent
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    except ImportError as e:
        raise ImportError(
            f"LangGraph dependencies not installed: {e}\n"
            "Please install with: pip install langchain>=1.0 langchain-openai>=0.3.32 "
            "langchain-core>=0.3.75 langchain-mcp-adapters>=0.1.0"
        )
    
    print("\n" + "=" * 80)
    print("🚀 Executing LangGraph Agent with Llama Stack")
    print("=" * 80)
    print(f"\n📥 User Query: {input_text}")
    print(f"🤖 Model: {model_name}")
    print("-" * 80)
    
    # Get connection parameters from environment
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    
    # Create LangChain client for Llama Stack
    llm = create_langchain_client(
        model_name=model_name,
        host=host,
        port=port,
        secure=secure
    )
    
    # Test connectivity
    print("\n🧪 Testing Llama Stack connectivity...")
    try:
        test_response = llm.invoke("Say 'Connection successful' if you can read this.")
        print(f"   ✅ Connection successful!")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Llama Stack: {e}")
    
    # Handle RAG if vector store is specified
    if vector_store_name:
        print(f"\n🔍 RAG: Searching vector store '{vector_store_name}'...")
        
        client = create_client(host=host, port=port, secure=secure)
        
        try:
            context = get_rag_context(
                client=client,
                vector_store_name=vector_store_name,
                query=input_text,
                max_results=max_results,
                score_threshold=score_threshold,
                ranker=ranker
            )
            
            # Augment system instructions with context
            if context:
                system_instructions = augment_instructions_with_context(system_instructions, context)
                print(f"   ✅ System instructions augmented with RAG context")
        except ValueError as e:
            print(f"   ⚠️  {e}. Continuing without RAG.")
    else:
        print("\nℹ️  No vector store specified, proceeding without RAG")
    
    # Use provided tools or auto-discover from server
    if tools is None:
        # Auto-discover tool groups from the server (only MCP servers for LangGraph)
        print("\n🔍 Auto-discovering available MCP servers...")
        try:
            client = create_client(host=host, port=port, secure=secure)
            tools, skipped = discover_tools(
                client=client,
                vector_store_name=None,  # LangGraph doesn't use file_search
                include_web_search=False,  # LangGraph doesn't use web_search
                include_file_search=False,  # LangGraph doesn't use file_search
                include_mcp=True  # Only MCP servers
            )
            
            if tools:
                print(f"   ✅ Found {len(tools)} MCP server(s): {[t['server_label'] for t in tools]}")
                if skipped:
                    for skip_msg in skipped:
                        print(f"   ⚠️  Skipping {skip_msg}")
            else:
                print("   ℹ️  No MCP servers found")
        except Exception as e:
            tools = []
            print(f"   ⚠️  Could not fetch tool groups: {e}")
            print("   Agent will work without external tool access")
    elif len(tools) == 0:
        print("\n⚠️  No tools configured (--no-tools flag used)")
        print("   Agent will work without external tool access")
    
    # Build MCP client configuration
    mcp_config = {}
    if len(tools) > 0:
        print("\n🛠️  Configuring MCP client...")
        for tool_config in tools:
            if tool_config.get("type") == "mcp":
                server_label = tool_config.get("server_label", "Unknown")
                server_url = tool_config.get("server_url", "Unknown")
                mcp_config[server_label] = {
                    "transport": "sse",
                    "url": server_url,
                }
                print(f"   - MCP Server: {server_label}: {server_url}")
            elif tool_config.get("type") == "toolgroup":
                print(f"   ⚠️  Warning: Tool groups are not supported in LangGraph agent mode")
                print(f"      Tool group '{tool_config.get('toolgroup_id')}' will be ignored")
                print(f"      Please use 'default' agent type for tool group support")
    
    # Create MCP client and get tools with error handling
    print("\n📦 Loading MCP tools...")
    langchain_tools = []
    
    if mcp_config:
        try:
            import asyncio
            
            mcp_client = MultiServerMCPClient(mcp_config)
            
            # Add timeout for port-forwarding scenarios (kubefwd/kubectl)
            try:
                langchain_tools = await asyncio.wait_for(
                    mcp_client.get_tools(),
                    timeout=30.0  # 30 second timeout for SSE connection
                )
            except asyncio.TimeoutError:
                print(f"   ⚠️  Warning: Timeout loading MCP tools (30s)")
                print(f"   💡 SSE connections through port forwarding can timeout")
                print(f"   💡 Tip: Use 'kubectl port-forward' instead of kubefwd for better SSE support")
                raise
            
            print(f"   ✅ Loaded {len(langchain_tools)} tools from MCP servers:")
            for tool in langchain_tools:
                print(f"      - {tool.name}: {tool.description}")
        except Exception as e:
            import traceback
            print(f"   ⚠️  Warning: Failed to load MCP tools: {e}")
            print(f"   🔍 Error type: {type(e).__name__}")
            
            # Show detailed trace for debugging
            if os.environ.get("DEBUG_MCP", "false").lower() == "true":
                print(f"   🔍 Full traceback:")
                print(traceback.format_exc())
            
            print(f"   ⚠️  Continuing without MCP tools. The agent will work without external tool access.")
            print(f"   💡 Tip: Check if MCP servers are running and accessible:")
            for server_label, config in mcp_config.items():
                print(f"      - {server_label}: {config['url']}")
            print(f"   💡 If using kubefwd: SSE may not work, try 'kubectl port-forward' instead")
    else:
        print("   ℹ️  No MCP servers configured, continuing without tools")
    
    # Create event handler if not provided
    if event_handler is None:
        event_handler = AgentEventHandler()
    
    # Create LangGraph agent using create_agent API
    print("\n🤖 Creating LangGraph ReAct agent...")
    
    if langchain_tools:
        agent = create_agent(
            model=llm,
            tools=langchain_tools,
            system_prompt=system_instructions,
        )
        print(f"   ✅ Agent created successfully with {len(langchain_tools)} tools!")
    else:
        agent = create_agent(
            model=llm,
            tools=[],  # Empty tools list
            system_prompt=system_instructions,
        )
        print(f"   ✅ Agent created successfully (without tools)")
        print(f"   ℹ️  Note: Agent will answer based on model knowledge only")
    
    # Execute the agent
    print("\n" + "=" * 80)
    print("🔄 Executing Agent...")
    print("=" * 80 + "\n")
    
    final_response = ""
    
    # Use astream_events if requested for real-time event streaming
    if use_streaming:
        try:
            async for event in agent.astream_events(
                {"messages": [{"role": "user", "content": input_text}]},
                version="v2"
            ):
                event_type = event.get("event", "")
                
                # Process different event types
                if event_type == "on_chat_model_start":
                    event_handler.on_chat_model_start(
                        event.get("metadata", {}),
                        [[]]
                    )
                
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    event_handler.on_chat_model_stream(chunk)
                    # Event captured - display happens later in formatted output
                
                elif event_type == "on_chat_model_end":
                    event_handler.on_chat_model_end(event.get("data", {}))
                
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    event_handler.on_tool_start(
                        {"name": tool_name},
                        str(tool_input)
                    )
                    print(f"\n🔧 Tool: {tool_name}")
                    import json
                    try:
                        print(f"📝 Args: {json.dumps(tool_input, indent=2)}")
                    except:
                        print(f"📝 Args: {tool_input}")
                
                elif event_type == "on_tool_end":
                    tool_output = event.get("data", {}).get("output", "")
                    event_handler.on_tool_end(str(tool_output))
                    print(f"✅ Tool Result: {tool_output}")
            
            # Get final result after streaming
            result = await agent.ainvoke({
                "messages": [{"role": "user", "content": input_text}]
            })
            
        except Exception as e:
            print(f"⚠️  Streaming not available: {e}")
            print(f"   Falling back to non-streaming execution")
            use_streaming = False
    
    # Non-streaming execution (fallback or if disabled)
    if not use_streaming:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": input_text}]
        })
    
    # Display execution trace
    print("\n📊 Agent Execution Trace:")
    print("-" * 80)
    
    final_response = ""
    for message in result["messages"]:
        if isinstance(message, HumanMessage):
            print(f"\n👤 Human: {message.content}")
        
        elif isinstance(message, AIMessage):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                print(f"\n🤖 AI (Tool Call):")
                for tool_call in message.tool_calls:
                    print(f"   🔧 Tool: {tool_call['name']}")
                    # Print args as formatted JSON
                    import json
                    try:
                        args_json = json.dumps(tool_call['args'], indent=2)
                        print(f"   📝 Args: {args_json}")
                    except:
                        print(f"   📝 Args: {tool_call['args']}")
            else:
                print(f"\n🤖 AI: {message.content}")
                final_response = message.content
        
        elif isinstance(message, SystemMessage):
            # Skip system messages in trace
            pass
        else:
            # Handle tool messages (show full content, no truncation)
            if hasattr(message, 'content'):
                import json
                content_str = str(message.content)
                # Try to pretty-print if it's JSON
                try:
                    content_obj = json.loads(content_str)
                    content_formatted = json.dumps(content_obj, indent=2)
                    print(f"\n🛠️  Tool Result:\n{content_formatted}")
                except:
                    # Not JSON, just print as-is
                    print(f"\n🛠️  Tool Result: {content_str}")
    
    print("\n" + "=" * 80)
    print("✅ LangGraph Agent Execution Complete!")
    print("=" * 80)
    
    # Return response and structured data
    return final_response, {
        "events": event_handler.get_events(),
        "tool_calls": event_handler.get_tool_calls(),
        "final_response": final_response
    }
    
def agent_command(
    agent_type: str,
    input_text: str,
    model_name: str,
    system_instructions: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    suppress_stdout: bool = False
) -> Tuple[str, List[str], Dict[str, Any]]:
    """
    Execute an agent command based on the specified agent type.
    
    Args:
        agent_type: Type of agent to use ('default', 'lang_chain', or 'lang_graph')
        input_text: The input prompt for the agent
        model_name: The name of the model to use (defaults to env var MODEL_NAME)
        system_instructions: System instructions for the agent (defaults to env var SYSTEM_INSTRUCTIONS)
        tools: List of tools/MCP servers to use (optional)
        log_callback: Optional callback function called with each log line as it's generated
        suppress_stdout: If True, don't write to stdout (only capture for callback) - useful for Streamlit
    
    Returns:
        Tuple of (response_text, execution_logs, structured_data)
        - response_text: Final agent response
        - execution_logs: List of captured log lines
        - structured_data: Dict containing events, tool_calls, and other structured info
        
    Raises:
        ValueError: If agent_type is not supported
    """
    import asyncio
    
    vector_store_name = os.environ.get("VECTOR_STORE_NAME", None)

    # Get default system instructions from environment if not provided
    if system_instructions is None:
        system_instructions = os.environ.get(
            "SYSTEM_INSTRUCTIONS",
            "You are a helpful AI assistant. Answer questions accurately and concisely."
        )
    
    # Validate agent type
    if agent_type not in ["default", "lang_chain", "lang_graph"]:
        raise ValueError(
            f"Invalid agent_type: '{agent_type}'. "
            f"Must be one of: 'default', 'lang_chain', 'lang_graph'"
        )
    
    # Execute with streaming log handler if callback provided
    if log_callback:
        with StreamingLogHandler(callback=log_callback, suppress_stdout=suppress_stdout) as log_handler:
            # Route to the appropriate agent implementation
            if agent_type == "default":
                response, structured_data = default_agent(
                    input_text=input_text,
                    model_name=model_name,
                    system_instructions=system_instructions,
                    tools=tools,
                    vector_store_name=vector_store_name
                )
            elif agent_type == "lang_chain":
                # LangChain agent is async, so we need to run it in an event loop
                response, structured_data = asyncio.run(langchain_agent(
                    input_text=input_text,
                    model_name=model_name,
                    system_instructions=system_instructions,
                    tools=tools,
                    vector_store_name=vector_store_name
                ))
            elif agent_type == "lang_graph":
                # LangGraph agent is async, so we need to run it in an event loop
                response, structured_data = asyncio.run(langgraph_agent(
                    input_text=input_text,
                    model_name=model_name,
                    system_instructions=system_instructions,
                    tools=tools,
                    vector_store_name=vector_store_name
                ))
            else:
                # This should never be reached due to validation above
                raise ValueError(f"Unsupported agent_type: {agent_type}")
            
            # Get captured logs
            logs = log_handler.get_logs()
            return response, logs, structured_data
    else:
        # Execute without log capture (legacy mode)
        if agent_type == "default":
            response, structured_data = default_agent(
                input_text=input_text,
                model_name=model_name,
                system_instructions=system_instructions,
                tools=tools,
                vector_store_name=vector_store_name
            )
        elif agent_type == "lang_chain":
            response, structured_data = asyncio.run(langchain_agent(
                input_text=input_text,
                model_name=model_name,
                system_instructions=system_instructions,
                tools=tools,
                vector_store_name=vector_store_name
            ))
        elif agent_type == "lang_graph":
            response, structured_data = asyncio.run(langgraph_agent(
                input_text=input_text,
                model_name=model_name,
                system_instructions=system_instructions,
                tools=tools,
                vector_store_name=vector_store_name
            ))
        else:
            raise ValueError(f"Unsupported agent_type: {agent_type}")
        
        return response, [], structured_data


def main() -> None:
    """
    Main entry point for standalone execution.
    Reads parameters from environment variables or command line args.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Execute an agent command with different agent types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run default agent
  python agent_command.py --agent-type default --input "What is the weather?"
  
  # Run with custom model
  python agent_command.py --agent-type default --input "Hello" --model "meta-llama/Llama-3.2-3B-Instruct"
  
  # Run LangChain agent
  python agent_command.py --agent-type lang_chain --input "Analyze this data"
  
  # Run LangGraph agent
  python agent_command.py --agent-type lang_graph --input "Complex workflow task"
        """
    )
    
    parser.add_argument(
        "--agent-type",
        type=str,
        required=True,
        choices=["default", "lang_chain", "lang_graph"],
        help="Type of agent to use"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input text/prompt for the agent"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name to use (default: from MODEL_NAME env var)"
    )
    parser.add_argument(
        "--instructions",
        type=str,
        default=None,
        help="System instructions (default: from SYSTEM_INSTRUCTIONS env var)"
    )
    
    args = parser.parse_args()
    
    try:
        response = agent_command(
            agent_type=args.agent_type,
            input_text=args.input,
            model_name=args.model,
            system_instructions=args.instructions
        )
        print(f"\nFinal Response:\n{response}")
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

            # {
            #     "type": "mcp",
            #     "server_label": "compatibility-engine-MCP-Server",
            #     "server_url": "https://compatibility-enginellama-stack-demo.apps.ocp.sandbox3322.opentlc.com/sse"
            # },
            # {
            #     "type": "mcp",
            #     "server_label": "eligibility-engine-MCP-Server",
            #     "server_url": "https://eligibility-engine-llama-stack-demo.apps.ocp.sandbox3322.opentlc.com/sse"
            # },
            # {
            #     "type": "mcp",
            #     "server_label": "finance-engine-MCP-Server",
            #     "server_url": "https://finance-engine-llama-stack-demo.apps.ocp.sandbox3322.opentlc.com/sse"
            # },