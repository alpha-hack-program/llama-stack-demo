#!/usr/bin/env python3
"""
Streamlit Chat Application for LlamaStack.

Provides a chat interface with:
- Sidebar for agent and tool configuration
- Chat panel for typing queries and viewing responses
"""

import os
import sys

# Write directly to stderr FIRST to test if this works
print("=" * 80, file=sys.stderr, flush=True)
print("🚀 APP.PY LOADING - DIRECT PRINT TO STDERR", file=sys.stderr, flush=True)
print("=" * 80, file=sys.stderr, flush=True)

import streamlit as st
from typing import List, Dict, Any, Optional
import threading
from flask import Flask, jsonify
import logging

# Configure logging to output to stdout and a file for debugging
log_file = '/tmp/health-server.log'
print(f"📝 Setting up logging to: {log_file}", file=sys.stderr, flush=True)

try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, mode='w')  # 'w' to overwrite on each run
        ],
        force=True  # Force reconfiguration
    )
    logger = logging.getLogger(__name__)
    print("✅ Logging configured successfully", file=sys.stderr, flush=True)
except Exception as e:
    print(f"❌ Logging configuration failed: {e}", file=sys.stderr, flush=True)
    logger = None

from llama_stack_client.types.model import Model

from utils import create_client, list_models
from commands.agent_command import agent_command

# Force immediate output
sys.stdout.flush()
sys.stderr.flush()

logger.info(f"📝 Logging to: {log_file}")
logger.info("=" * 80)
logger.info("🚀 APP.PY MODULE LOADING...")
logger.info("=" * 80)


# Health check server (runs on a separate port)
logger.info("🏥 Creating Flask health app...")
health_app = Flask(__name__)
health_status = {"status": "healthy", "checks": {}}


@health_app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Kubernetes/OpenShift probes."""
    logger.info("🏥 Health check endpoint called")
    return jsonify(health_status), 200


@health_app.route('/ready', methods=['GET'])
def readiness_check():
    """Readiness check endpoint - verifies the app can handle requests."""
    logger.info("🔍 Readiness check endpoint called")
    try:
        # Check if we can create a client connection
        client = get_llama_client()
        health_status["checks"]["llama_stack"] = "connected"
        logger.info("✅ Readiness check: Llama Stack connected")
        return jsonify({"status": "ready", "checks": health_status["checks"]}), 200
    except Exception as e:
        health_status["checks"]["llama_stack"] = f"error: {str(e)}"
        logger.error(f"❌ Readiness check failed: {str(e)}")
        return jsonify({"status": "not_ready", "error": str(e), "checks": health_status["checks"]}), 503


# Log registered routes after they are defined
logger.info("🏥 Flask health app initialized")
logger.info(f"   Registered routes:")
for rule in health_app.url_map.iter_rules():
    logger.info(f"     - {rule.rule} [{', '.join(rule.methods - {'OPTIONS', 'HEAD'})}]")


def start_health_server():
    """Start the health check server on a separate thread."""
    health_port = int(os.environ.get("HEALTH_PORT", "8081"))
    logger.info(f"🚀 Attempting to start health server on port {health_port}...")
    try:
        logger.info(f"📡 Flask app starting on 0.0.0.0:{health_port}")
        sys.stdout.flush()
        sys.stderr.flush()
        health_app.run(host='0.0.0.0', port=health_port, debug=False, use_reloader=False)
        logger.info(f"✅ Health server started successfully on port {health_port}")
    except OSError as e:
        if "Address already in use" in str(e):
            logger.warning(f"⚠️  Health server port {health_port} already in use (likely from Streamlit reload), skipping...")
        else:
            logger.error(f"❌ Health server OSError: {e}")
            import traceback
            logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(f"❌ Health server error: {e}")
        import traceback
        logger.error(traceback.format_exc())


# Global flag to ensure health server only starts once
_health_server_started = False

# Start health check server in background thread
# Note: This runs at module load time
logger.info("=" * 80)
logger.info("🔧 Initializing health check server...")

if not _health_server_started:
    logger.info("   ✅ Starting health server thread...")
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    _health_server_started = True
    logger.info(f"   ✅ Health check thread started (daemon: {health_thread.daemon}, alive: {health_thread.is_alive()})")
    logger.info(f"   ✅ Health server starting on port {os.environ.get('HEALTH_PORT', '8081')}")
    # Give the server a moment to start
    import time
    time.sleep(0.5)
    logger.info(f"   ✅ Thread status after sleep: alive={health_thread.is_alive()}")
else:
    logger.info("   ℹ️  Health server already started, skipping")
    
logger.info("=" * 80)

sys.stdout.flush()
sys.stderr.flush()


# Page configuration
st.set_page_config(
    page_title="LlamaStack Chat",
    page_icon="🦙",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent_type" not in st.session_state:
    st.session_state.agent_type = "default"

if "selected_model" not in st.session_state:
    st.session_state.selected_model = None

if "selected_tools" not in st.session_state:
    st.session_state.selected_tools = []

if "system_instructions" not in st.session_state:
    st.session_state.system_instructions = os.environ.get(
        "SYSTEM_INSTRUCTIONS",
        "You are a helpful AI assistant. Answer questions accurately and concisely."
    )

if "use_rag" not in st.session_state:
    st.session_state.use_rag = False

if "vector_store_name" not in st.session_state:
    st.session_state.vector_store_name = os.environ.get("VECTOR_STORE_NAME", "")


# Helper functions
@st.cache_resource
def get_llama_client():
    """Get cached LlamaStack client."""
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = int(os.environ.get("LLAMA_STACK_PORT", "8080"))
    secure = os.environ.get("LLAMA_STACK_SECURE", "false").lower() in ["true", "1", "yes"]
    return create_client(host=host, port=port, secure=secure)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_models() -> List[Dict[str, str]]:
    """Fetch available models from LlamaStack."""
    try:
        client = get_llama_client()
        models: List[Model] = list_models(client)
        return [
            {
                "identifier": m.identifier,
                "provider": m.provider_id,
                "type": m.api_model_type
            }
            for m in models
        ]
    except Exception as e:
        st.error(f"Error fetching models: {e}")
        return []


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_tool_groups() -> List[Dict[str, Any]]:
    """Fetch available tool groups from LlamaStack."""
    try:
        client = get_llama_client()
        tool_groups = list(client.toolgroups.list())
        
        result = []
        for group in tool_groups:
            # Get tools for this group
            tools = []
            try:
                tools_response = client.tools.list(toolgroup_id=group.identifier)
                tools = [
                    {
                        "name": t.name if hasattr(t, 'name') else 'Unknown',
                        "description": t.description if hasattr(t, 'description') else None,
                        "type": t.type if hasattr(t, 'type') else None,
                        "tool_data": t  # Store the full tool object for later use
                    }
                    for t in list(tools_response)
                ] if tools_response else []
            except Exception:
                pass
            
            result.append({
                "identifier": group.identifier if hasattr(group, 'identifier') else 'N/A',
                "provider": getattr(group, 'provider_id', None),
                "tools": tools
            })
        
        return result
    except Exception as e:
        st.error(f"Error fetching tool groups: {e}")
        return []


def get_tools_from_toolgroups(toolgroup_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Get tool configurations from selected toolgroups.
    
    For MCP toolgroups (those with format mcp::*), we need to provide the MCP server config.
    For builtin toolgroups (like builtin::websearch), we reference them by toolgroup_id.
    
    Args:
        toolgroup_ids: List of toolgroup identifiers
        
    Returns:
        List of tool configurations ready for Llama Stack API
    """
    try:
        client = get_llama_client()
        tools = []
        
        # Get all toolgroups
        all_toolgroups = list(client.toolgroups.list())
        toolgroup_map = {tg.identifier: tg for tg in all_toolgroups if hasattr(tg, 'identifier')}
        
        for group_id in toolgroup_ids:
            # Check if this is an MCP toolgroup
            if group_id.startswith('mcp::'):
                # For MCP toolgroups, we need to provide MCP server configuration
                toolgroup = toolgroup_map.get(group_id)
                if toolgroup:
                    # Try to extract MCP endpoint information
                    mcp_endpoint = getattr(toolgroup, 'mcp_endpoint', None)
                    provider_id = getattr(toolgroup, 'provider_id', None)
                    
                    if mcp_endpoint:
                        # Get URI from mcp_endpoint
                        uri = getattr(mcp_endpoint, 'uri', None) if hasattr(mcp_endpoint, 'uri') else mcp_endpoint.get('uri') if isinstance(mcp_endpoint, dict) else None
                        
                        if uri:
                            # Extract server name from toolgroup_id (remove 'mcp::' prefix)
                            server_name = group_id.replace('mcp::', '')
                            tools.append({
                                "type": "mcp",
                                "server_label": f"{server_name}-MCP-Server",
                                "server_url": uri
                            })
                        else:
                            st.warning(f"Could not extract MCP endpoint URI from toolgroup '{group_id}'")
                    else:
                        st.warning(f"Toolgroup '{group_id}' does not have MCP endpoint information")
                else:
                    st.warning(f"Toolgroup '{group_id}' not found")
            
            elif group_id.startswith('builtin::'):
                # For builtin toolgroups, use the toolgroup reference directly
                # These are handled differently by Llama Stack
                tools.append({
                    "type": group_id.split('::')[1],  # e.g., "websearch" from "builtin::websearch"
                    "toolgroup_id": group_id
                })
            else:
                st.warning(f"Unknown toolgroup format: '{group_id}'")
        
        return tools
    except Exception as e:
        st.error(f"Error fetching tools from toolgroups: {e}")
        import traceback
        st.error(traceback.format_exc())
        return []




def execute_agent_query(
    agent_type: str,
    input_text: str,
    model_name: str,
    system_instructions: str,
    tools: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Execute an agent query and return the response."""
    try:
        response = agent_command(
            agent_type=agent_type,
            input_text=input_text,
            model_name=model_name,
            system_instructions=system_instructions,
            tools=tools
        )
        return response
    except Exception as e:
        return f"Error: {str(e)}"


# Sidebar configuration
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # Agent type selection
    st.subheader("Agent Type")
    agent_type = st.selectbox(
        "Select Agent",
        options=["default", "lang_chain", "lang_graph"],
        index=["default", "lang_chain", "lang_graph"].index(st.session_state.agent_type),
        help="""
        - **default**: Native Llama Stack with server-side MCP
        - **lang_chain**: LangChain 1.0 with client-side MCP
        - **lang_graph**: LangGraph ReAct agent with MCP
        """
    )
    st.session_state.agent_type = agent_type
    
    # Agent type description
    agent_descriptions = {
        "default": "🚀 Uses Llama Stack's native MCP integration with server-side tool calling",
        "lang_chain": "🔗 LangChain 1.0 agent with MCP adapters for client-side tool execution",
        "lang_graph": "📊 LangGraph ReAct agent with MCP adapters using LangChain"
    }
    st.info(agent_descriptions[agent_type])
    
    st.divider()
    
    # Model selection
    st.subheader("Model")
    models = fetch_models()
    
    if models:
        # Filter for LLM models
        llm_models = [m for m in models if m["type"] == "llm"]
        
        if llm_models:
            model_options = [f"{m['identifier']} ({m['provider']})" for m in llm_models]
            
            # Get default model from environment or use first available
            default_model = os.environ.get("MODEL_NAME")
            default_index = 0
            if default_model:
                try:
                    default_index = next(
                        i for i, m in enumerate(llm_models)
                        if m['identifier'] == default_model
                    )
                except StopIteration:
                    pass
            
            selected_model_display = st.selectbox(
                "Select Model",
                options=model_options,
                index=default_index,
                help="Choose the LLM model to use for generating responses"
            )
            
            # Extract model identifier
            st.session_state.selected_model = llm_models[model_options.index(selected_model_display)]["identifier"]
        else:
            st.warning("No LLM models available")
            st.session_state.selected_model = None
    else:
        st.warning("Unable to fetch models")
        st.session_state.selected_model = None
    
    st.divider()
    
    # Tools configuration
    st.subheader("Tools")
    
    # Fetch available tool groups from llama stack
    tool_groups = fetch_tool_groups()
    
    if tool_groups:
        st.write("**Available Tool Groups from Llama Stack:**")
        
        # Allow selection of tool groups
        selected_group_ids = []
        for group in tool_groups:
            group_selected = st.checkbox(
                f"{group['identifier']}",
                value=False,
                key=f"toolgroup_{group['identifier']}",
                help=f"Provider: {group['provider']}"
            )
            
            if group_selected:
                selected_group_ids.append(group['identifier'])
            
            # Show tools in this group
            if group['tools']:
                with st.expander(f"Tools in {group['identifier']}", expanded=False):
                    for tool in group['tools']:
                        st.caption(f"  • {tool['name']}: {tool['description'] or 'No description'}")
        
        # Store selected tool groups and fetch individual tools
        if selected_group_ids:
            # Fetch individual tools from selected toolgroups
            individual_tools = get_tools_from_toolgroups(selected_group_ids)
            st.session_state.selected_tools = individual_tools
            
            if individual_tools:
                st.success(f"Selected {len(selected_group_ids)} tool group(s) with {len(individual_tools)} tool(s)")
            else:
                st.warning(f"Selected {len(selected_group_ids)} tool group(s) but no tools found")
                st.session_state.selected_tools = []
        else:
            st.session_state.selected_tools = []
            st.info("No tools selected. Agent will run without tools.")
    else:
        st.warning("No tool groups available in Llama Stack")
        st.session_state.selected_tools = []
    
    st.divider()
    
    # System instructions
    st.subheader("System Instructions")
    system_instructions = st.text_area(
        "Instructions",
        value=st.session_state.system_instructions,
        height=150,
        help="Provide instructions for the agent's behavior"
    )
    st.session_state.system_instructions = system_instructions
    
    st.divider()
    
    # RAG Configuration (optional)
    st.subheader("RAG (Optional)")
    use_rag = st.checkbox(
        "Enable RAG",
        value=st.session_state.use_rag,
        help="Enable Retrieval-Augmented Generation using vector stores"
    )
    st.session_state.use_rag = use_rag
    
    if use_rag:
        vector_store_name = st.text_input(
            "Vector Store Name",
            value=st.session_state.vector_store_name,
            help="Name of the vector store to use for RAG"
        )
        st.session_state.vector_store_name = vector_store_name
        
        if not vector_store_name:
            st.warning("Please specify a vector store name")
    
    st.divider()
    
    # Clear chat button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# Main chat interface
st.title("🦙 LlamaStack Chat")

# Display connection info
col1, col2, col3 = st.columns(3)
with col1:
    host = os.environ.get("LLAMA_STACK_HOST", "localhost")
    port = os.environ.get("LLAMA_STACK_PORT", "8080")
    st.caption(f"🔗 Connected to: {host}:{port}")
with col2:
    if st.session_state.selected_model:
        st.caption(f"🤖 Model: {st.session_state.selected_model.split('/')[-1]}")
    else:
        st.caption("🤖 Model: Not selected")
with col3:
    st.caption(f"🔧 Agent: {st.session_state.agent_type}")

st.divider()

# Display chat messages
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Type your message here..."):
    # Check if model is selected
    if not st.session_state.selected_model:
        st.error("Please select a model from the sidebar before chatting.")
        st.stop()
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Prepare tools
            tools = st.session_state.selected_tools if st.session_state.selected_tools else []
            
            # Execute agent
            response = execute_agent_query(
                agent_type=st.session_state.agent_type,
                input_text=prompt,
                model_name=st.session_state.selected_model,
                system_instructions=st.session_state.system_instructions,
                tools=tools
            )
            
            st.markdown(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})


# Footer
st.divider()
st.caption("Built with Streamlit and LlamaStack | Use the sidebar to configure your agent")


# Display environment info in expander
with st.expander("🔍 Environment Information", expanded=False):
    st.write("**Environment Variables:**")
    env_vars = {
        "LLAMA_STACK_HOST": os.environ.get("LLAMA_STACK_HOST", "Not set"),
        "LLAMA_STACK_PORT": os.environ.get("LLAMA_STACK_PORT", "Not set"),
        "LLAMA_STACK_SECURE": os.environ.get("LLAMA_STACK_SECURE", "Not set"),
        "MODEL_NAME": os.environ.get("MODEL_NAME", "Not set"),
        "VECTOR_STORE_NAME": os.environ.get("VECTOR_STORE_NAME", "Not set"),
    }
    for key, value in env_vars.items():
        st.code(f"{key}={value}")

