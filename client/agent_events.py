"""
Unified event system for all agent types.

This module provides a consistent event format across default, LangChain, and LangGraph agents,
based on LangChain's callback system and LangGraph's astream_events.
"""

from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import threading


class AgentEventHandler:
    """
    Unified event handler that captures events from all agent types in a consistent format.
    
    Based on LangChain's BaseCallbackHandler and LangGraph's astream_events,
    this provides a standardized interface for tracking agent execution.
    """
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
    
    def on(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback to be called for each event."""
        self.callbacks.append(callback)
    
    def _emit(self, event: Dict[str, Any]):
        """Emit an event to all registered callbacks."""
        with self._lock:
            self.events.append(event)
        
        # Call all callbacks
        for callback in self.callbacks:
            try:
                callback(event)
            except Exception as e:
                import sys
                print(f"Warning: Event callback error: {e}", file=sys.stderr)
    
    # ==================== LLM Events ====================
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
        """Called when LLM starts running."""
        self._emit({
            "event": "on_llm_start",
            "name": serialized.get("name", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "data": {
                "prompts": prompts,
                "serialized": serialized
            }
        })
    
    def on_llm_end(self, response, **kwargs):
        """Called when LLM ends running."""
        self._emit({
            "event": "on_llm_end",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "response": str(response)
            }
        })
    
    def on_llm_error(self, error: Exception, **kwargs):
        """Called when LLM errors."""
        self._emit({
            "event": "on_llm_error",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "error": str(error)
            }
        })
    
    def on_llm_new_token(self, token: str, **kwargs):
        """Called when LLM generates a new token (streaming)."""
        self._emit({
            "event": "on_llm_new_token",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "token": token
            }
        })
    
    # ==================== Chat Model Events ====================
    
    def on_chat_model_start(self, serialized: Dict[str, Any], messages: List[List], **kwargs):
        """Called when chat model starts."""
        self._emit({
            "event": "on_chat_model_start",
            "name": serialized.get("name", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "data": {
                "messages": [[str(m) for m in msg_list] for msg_list in messages],
                "serialized": serialized
            }
        })
    
    def on_chat_model_stream(self, chunk, **kwargs):
        """Called when chat model streams a chunk."""
        content = ""
        if hasattr(chunk, 'content'):
            content = chunk.content
        elif hasattr(chunk, 'message'):
            content = str(chunk.message)
        else:
            content = str(chunk)
            
        self._emit({
            "event": "on_chat_model_stream",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "chunk": content
            }
        })
    
    def on_chat_model_end(self, response, **kwargs):
        """Called when chat model ends."""
        self._emit({
            "event": "on_chat_model_end",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "response": str(response)
            }
        })
    
    # ==================== Tool Events ====================
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """Called when tool starts running."""
        tool_name = serialized.get("name", "unknown")
        self._emit({
            "event": "on_tool_start",
            "name": tool_name,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "tool": tool_name,
                "input": input_str,
                "serialized": serialized
            }
        })
    
    def on_tool_end(self, output: str, **kwargs):
        """Called when tool ends running."""
        self._emit({
            "event": "on_tool_end",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "output": output
            }
        })
    
    def on_tool_error(self, error: Exception, **kwargs):
        """Called when tool errors."""
        self._emit({
            "event": "on_tool_error",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "error": str(error)
            }
        })
    
    # ==================== Agent Events ====================
    
    def on_agent_action(self, action, **kwargs):
        """Called when agent takes an action."""
        tool_name = action.tool if hasattr(action, 'tool') else "unknown"
        tool_input = action.tool_input if hasattr(action, 'tool_input') else {}
        
        self._emit({
            "event": "on_agent_action",
            "name": tool_name,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "tool": tool_name,
                "tool_input": tool_input,
                "log": action.log if hasattr(action, 'log') else ""
            }
        })
    
    def on_agent_finish(self, finish, **kwargs):
        """Called when agent finishes running."""
        return_values = finish.return_values if hasattr(finish, 'return_values') else {}
        
        self._emit({
            "event": "on_agent_finish",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "return_values": return_values,
                "log": finish.log if hasattr(finish, 'log') else ""
            }
        })
    
    # ==================== Chain Events ====================
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs):
        """Called when chain starts running."""
        self._emit({
            "event": "on_chain_start",
            "name": serialized.get("name", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "data": {
                "inputs": inputs,
                "serialized": serialized
            }
        })
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs):
        """Called when chain ends running."""
        self._emit({
            "event": "on_chain_end",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "outputs": outputs
            }
        })
    
    def on_chain_error(self, error: Exception, **kwargs):
        """Called when chain errors."""
        self._emit({
            "event": "on_chain_error",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "error": str(error)
            }
        })
    
    # ==================== Retriever Events ====================
    
    def on_retriever_start(self, serialized: Dict[str, Any], query: str, **kwargs):
        """Called when retriever starts."""
        self._emit({
            "event": "on_retriever_start",
            "name": serialized.get("name", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "data": {
                "query": query,
                "serialized": serialized
            }
        })
    
    def on_retriever_end(self, documents, **kwargs):
        """Called when retriever ends."""
        self._emit({
            "event": "on_retriever_end",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "documents": [str(doc) for doc in documents]
            }
        })
    
    # ==================== Helper Methods ====================
    
    def get_events(self) -> List[Dict[str, Any]]:
        """Get all captured events."""
        with self._lock:
            return self.events.copy()
    
    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get events filtered by type."""
        with self._lock:
            return [e for e in self.events if e["event"] == event_type]
    
    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """Get structured tool call information."""
        tool_calls = []
        tool_starts = self.get_events_by_type("on_tool_start")
        tool_ends = self.get_events_by_type("on_tool_end")
        
        for i, start_event in enumerate(tool_starts):
            tool_call = {
                "tool": start_event.get("name", "unknown"),
                "input": start_event["data"].get("input"),
                "timestamp": start_event["timestamp"]
            }
            
            # Match with corresponding end event
            if i < len(tool_ends):
                tool_call["output"] = tool_ends[i]["data"].get("output")
            
            tool_calls.append(tool_call)
        
        return tool_calls
    
    def clear(self):
        """Clear all events."""
        with self._lock:
            self.events.clear()


# Create a LangChain-compatible callback handler
try:
    from langchain_core.callbacks import BaseCallbackHandler
    
    class LangChainAgentCallback(BaseCallbackHandler, AgentEventHandler):
        """
        LangChain-compatible callback handler that extends AgentEventHandler.
        
        This allows it to be used directly with LangChain agents while maintaining
        the unified event format.
        """
        
        def __init__(self):
            BaseCallbackHandler.__init__(self)
            AgentEventHandler.__init__(self)

except ImportError:
    # LangChain not installed, define a placeholder
    class LangChainAgentCallback(AgentEventHandler):
        """Fallback when LangChain is not installed."""
        pass


# Event type constants for convenience
EVENT_ON_LLM_START = "on_llm_start"
EVENT_ON_LLM_END = "on_llm_end"
EVENT_ON_LLM_ERROR = "on_llm_error"
EVENT_ON_LLM_NEW_TOKEN = "on_llm_new_token"
EVENT_ON_CHAT_MODEL_START = "on_chat_model_start"
EVENT_ON_CHAT_MODEL_STREAM = "on_chat_model_stream"
EVENT_ON_CHAT_MODEL_END = "on_chat_model_end"
EVENT_ON_TOOL_START = "on_tool_start"
EVENT_ON_TOOL_END = "on_tool_end"
EVENT_ON_TOOL_ERROR = "on_tool_error"
EVENT_ON_AGENT_ACTION = "on_agent_action"
EVENT_ON_AGENT_FINISH = "on_agent_finish"
EVENT_ON_CHAIN_START = "on_chain_start"
EVENT_ON_CHAIN_END = "on_chain_end"
EVENT_ON_CHAIN_ERROR = "on_chain_error"
EVENT_ON_RETRIEVER_START = "on_retriever_start"
EVENT_ON_RETRIEVER_END = "on_retriever_end"

