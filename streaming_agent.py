from typing import Dict, List, Any, TypedDict, Annotated, Literal, AsyncGenerator, Tuple
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from bedrock_client import bedrock_client
from mcp_client import mcp_client
from config import Config
import json
import asyncio
import logging

# Configure logger for streaming agent
logger = logging.getLogger(__name__)

class StreamingAgentState(TypedDict):
    """State for the streaming agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    user_input: str
    needs_tools: bool
    final_response: str
    error_message: str
    current_step: str
    step_details: str
    iteration_count: int

# MCP tools will be dynamically loaded from MCP servers

class StreamingAgent:
    """Streaming-enabled agent with real-time progress updates using LangGraph"""
    
    def __init__(self):
        self.llm = bedrock_client.get_llm()
        
        # Tools will be loaded dynamically from MCP servers
        self.tools = []
        self.tool_node = None
        self.llm_with_tools = None
        
        # MCP initialization state
        self._mcp_initialized = False
        
        # Graph will be built after MCP initialization
        self.graph = None
    
    async def _ensure_mcp_initialized(self):
        """Ensure MCP client is initialized and tools are loaded (only once)"""
        logger.info("🔧 Checking MCP initialization status...")
        if not self._mcp_initialized:
            logger.info("🚀 Initializing MCP client for the first time...")
            await mcp_client.initialize()
            logger.info("📦 Loading MCP tools...")
            await self._load_mcp_tools()
            self._mcp_initialized = True
            logger.info("✅ MCP initialization completed")
        else:
            logger.info("✅ MCP already initialized, skipping...")
    
    async def _load_mcp_tools(self):
        """Load tools from MCP servers and convert to LangChain tools"""
        try:
            # Get available tools from MCP servers
            mcp_tools = await mcp_client.get_available_tools()
            logger.info(f"🔍 MCP tools received: {mcp_tools}")
            
            # Convert MCP tools to LangChain tools
            self.tools = []
            for server_name, server_tools in mcp_tools.items():
                logger.info(f"🔍 Processing server: {server_name} with {len(server_tools)} tools")
                for tool_info in server_tools:
                    logger.debug(f"🔍 Tool info: {tool_info}")
                    langchain_tool = self._create_langchain_tool(tool_info, server_name)
                    if langchain_tool:
                        self.tools.append(langchain_tool)
                        logger.info(f"✅ Created LangChain tool: {langchain_tool.name}")
                    else:
                        logger.error(f"❌ Failed to create LangChain tool for: {tool_info}")
            
            # Create ToolNode and bind tools to LLM
            if self.tools:
                self.tool_node = ToolNode(self.tools)
                self.llm_with_tools = self.llm.bind_tools(self.tools)
                logger.info(f"✅ Loaded {len(self.tools)} tools from MCP servers")
                logger.info(f"🔍 Tool names: {[tool.name for tool in self.tools]}")
                
                # Build the graph after tools are loaded
                self._build_graph()
            else:
                logger.warning("⚠️  No tools loaded from MCP servers")
                
        except Exception as e:
            logger.error(f"❌ Error loading MCP tools: {e}")
            import traceback
            traceback.print_exc()
            self.tools = []
    
    def _create_langchain_tool(self, tool_info: Dict[str, Any], server_name: str):
        """Convert MCP tool info to LangChain tool"""
        try:
            tool_name = tool_info.get("name", "")
            tool_description = tool_info.get("description", "")
            tool_input_schema = tool_info.get("inputSchema", {})
            
            logger.debug(f"🔍 Creating tool: {tool_name} with schema: {tool_input_schema}")
            
            # Create a dynamic tool function
            async def tool_func(**kwargs) -> str:
                try:
                    logger.debug(f"🔍 Executing tool {tool_name} with args: {kwargs}")
                    result = await mcp_client.call_tool(server_name, tool_name, kwargs)
                    logger.debug(f"🔍 Tool result: {result}")
                    if result["success"]:
                        return json.dumps(result["result"], indent=2)
                    else:
                        return f"Error: {result['error']}"
                except Exception as e:
                    logger.error(f"❌ Error executing {tool_name}: {str(e)}")
                    return f"Error executing {tool_name}: {str(e)}"
            
            # Create LangChain tool with proper typing
            from langchain_core.tools import tool
            from pydantic import BaseModel, Field
            from typing import Optional
            
            # Create a simple Pydantic model for the tool
            class ToolInput(BaseModel):
                pass
            
            # Add fields based on input schema
            if tool_input_schema and "properties" in tool_input_schema:
                for prop_name, prop_info in tool_input_schema["properties"].items():
                    prop_type = str  # Default to string
                    if prop_info.get("type") == "string":
                        prop_type = str
                    elif prop_info.get("type") == "integer":
                        prop_type = int
                    elif prop_info.get("type") == "boolean":
                        prop_type = bool
                    
                    # Add field to the model with default value
                    default_value = prop_info.get("default")
                    if default_value is None and prop_name == "path" and tool_name == "list_directory":
                        default_value = "."  # Default to current directory
                    
                    setattr(ToolInput, prop_name, Field(
                        default=default_value if default_value is not None else ...,
                        description=prop_info.get("description", "")
                    ))
            else:
                # If no schema provided, add common defaults
                if tool_name == "list_directory":
                    setattr(ToolInput, "path", Field(default=".", description="Directory path to list"))
                elif tool_name == "read_file":
                    setattr(ToolInput, "path", Field(description="File path to read"))
            
            # Set the function name and docstring
            tool_func.__name__ = tool_name
            tool_func.__doc__ = tool_description
            
            # Create the tool with proper schema
            langchain_tool = tool(tool_func)
            logger.debug(f"✅ Created LangChain tool: {langchain_tool.name}")
            return langchain_tool
            
        except Exception as e:
            logger.error(f"❌ Error creating LangChain tool for {tool_info.get('name', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_graph(self):
        """Build the LangGraph workflow with conditional edges"""
        logger.info("🏗️ Building LangGraph workflow...")
        
        # Create the graph
        workflow = StateGraph(StreamingAgentState)
        
        # Add nodes
        workflow.add_node("analyze_input", self._analyze_input_node)
        workflow.add_node("direct_response", self._direct_response_node)
        workflow.add_node("llm_with_tools", self._llm_with_tools_node)
        workflow.add_node("execute_tools", self._execute_tools_node)
        workflow.add_node("final_response", self._final_response_node)
        
        # Set entry point
        workflow.set_entry_point("analyze_input")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "analyze_input",
            self._should_use_tools,
            {
                "direct": "direct_response",
                "tools": "llm_with_tools"
            }
        )
        
        workflow.add_conditional_edges(
            "llm_with_tools",
            self._should_execute_tools,
            {
                "execute": "execute_tools",
                "final": "final_response"
            }
        )
        
        # Add loop back from execute_tools to llm_with_tools for tool result interpretation
        workflow.add_conditional_edges(
            "execute_tools",
            self._should_continue_after_tools,
            {
                "continue": "llm_with_tools",  # Loop back to interpret tool results
                "final": "final_response"
            }
        )
        
        # Add edges
        workflow.add_edge("direct_response", END)
        workflow.add_edge("final_response", END)
        
        # Compile the graph
        self.graph = workflow.compile()
        logger.info("✅ LangGraph workflow built successfully")
    
    def _should_use_tools(self, state: StreamingAgentState) -> str:
        """Determine if tools should be used based on LLM analysis"""
        return state.get("needs_tools", False) and "tools" or "direct"
    
    def _should_execute_tools(self, state: StreamingAgentState) -> str:
        """Determine if tools should be executed based on LLM response"""
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "execute"
        else:
            # If no tool calls, set the final response from the LLM's content
            if hasattr(last_message, 'content') and last_message.content:
                state["final_response"] = last_message.content
            return "final"
    
    def _should_continue_after_tools(self, state: StreamingAgentState) -> str:
        """Determine if we should continue after tool execution"""
        # Prevent infinite loops
        max_iterations = 5
        current_iterations = state.get("iteration_count", 0)
        
        if current_iterations >= max_iterations:
            logger.warning(f"⚠️  Maximum iterations ({max_iterations}) reached, stopping")
            return "final"
        
        # Check if we have tool results that need interpretation
        if len(state["messages"]) >= 2:
            last_message = state["messages"][-1]
            # If the last message is a tool result, continue to interpret it
            if hasattr(last_message, 'content') and last_message.content:
                return "continue"
        
        # If we're ending, check if we have a final response from the last LLM call
        if len(state["messages"]) >= 1:
            last_message = state["messages"][-1]
            if hasattr(last_message, 'content') and last_message.content and not state.get("final_response"):
                state["final_response"] = last_message.content
                logger.info("✅ Final response set from last LLM message")
        
        return "final"
    
    async def _analyze_input_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """Analyze input to determine if tools are needed"""
        logger.info("🔍 Analyzing input to determine tool usage...")
        
        # Use LLM to analyze if tools are needed
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that analyzes user requests to determine if tools are needed.

Available tools: {tool_names}

Analyze the user's request and determine if any tools are needed to fulfill it.
Respond with "YES" if tools are needed, "NO" if a direct response is sufficient.

Examples:
- "List files in directory" -> YES (needs filesystem tools)
- "What is the weather?" -> NO (direct response)
- "Read a file" -> YES (needs filesystem tools)
- "Hello, how are you?" -> NO (direct response)
- "Search for information" -> YES (needs search tools)
"""),
            ("human", "User request: {user_input}")
        ])
        
        tool_names = [tool.name for tool in self.tools] if self.tools else []
        
        try:
            response = await self.llm.ainvoke(analysis_prompt.format_messages(
                tool_names=", ".join(tool_names),
                user_input=state["user_input"]
            ))
            
            needs_tools = "YES" in response.content.upper()
            state["needs_tools"] = needs_tools
            
            logger.info(f"🔍 LLM analysis: needs_tools = {needs_tools}")
            
        except Exception as e:
            logger.error(f"❌ Error in input analysis: {e}")
            # Fallback to keyword-based detection
            user_lower = state["user_input"].lower()
            needs_tools = any(keyword in user_lower for keyword in [
                "list", "ls", "directory", "files", "read", "write", "create", "search", "find", "query", "database", "sql", 
                "table", "describe", "structure", "schema", "employee", "select", "show", "display",
                "디렉토리", "파일", "리스트", "목록", "보여줘", "보여주세요", "읽기", "쓰기", "검색", "찾기", "조회", "데이터베이스"
            ])
            state["needs_tools"] = needs_tools
            logger.info(f"🔍 Fallback analysis: needs_tools = {needs_tools}")
        
        return state
    
    async def _direct_response_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """Generate direct response without tools"""
        logger.info("💬 Generating direct response...")
        
        try:
            conversation_history = state["messages"][:-1]
            context_messages = []
            for msg in conversation_history[-6:]:
                if isinstance(msg, HumanMessage):
                    context_messages.append(("human", msg.content))
                elif isinstance(msg, AIMessage):
                    context_messages.append(("assistant", msg.content))
            
            context_messages.append(("human", state["user_input"]))
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful AI assistant. Provide clear, accurate, and helpful responses to user questions and requests. 
                
Be conversational, friendly, and informative. When users ask for multiple tasks, you can use multiple tools in sequence to complete them all."""),
                *context_messages
            ])
            
            response = await self.llm.ainvoke(prompt.format_messages())
            state["final_response"] = response.content
            
        except Exception as e:
            logger.error(f"❌ Error in direct response: {e}")
            state["error_message"] = str(e)
        
        return state
    
    async def _llm_with_tools_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """LLM node with tools available"""
        logger.info("🤖 LLM thinking with tools...")
        
        # Increment iteration count
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        
        try:
            response = await self.llm_with_tools.ainvoke(state["messages"])
            state["messages"].append(response)
            
            logger.debug(f"🔍 LLM response: {response.content}")
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"🔍 Tool calls generated: {response.tool_calls}")
            else:
                # If no tool calls, this might be the final response
                if response.content and not state.get("final_response"):
                    state["final_response"] = response.content
                    logger.info("✅ Final response set from LLM with tools")
            
        except Exception as e:
            logger.error(f"❌ Error in LLM with tools: {e}")
            state["error_message"] = str(e)
        
        return state
    
    async def _execute_tools_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """Execute tools using ToolNode"""
        logger.info("🔧 Executing tools...")
        
        try:
            tool_results = await self.tool_node.ainvoke({"messages": [state["messages"][-1]]})
            state["messages"].extend(tool_results["messages"])
            
        except Exception as e:
            logger.error(f"❌ Error executing tools: {e}")
            state["error_message"] = str(e)
        
        return state
    
    async def _final_response_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """Generate final response after tool execution"""
        logger.info("📝 Generating final response...")
        
        try:
            # If we already have a final response from the last LLM call, use it
            if state.get("final_response"):
                logger.info("✅ Using existing final response")
                return state
            
            # Otherwise, generate a new response
            response = await self.llm_with_tools.ainvoke(state["messages"])
            state["final_response"] = response.content
            
        except Exception as e:
            logger.error(f"❌ Error in final response: {e}")
            state["error_message"] = str(e)
            # Set a fallback response
            if not state.get("final_response"):
                state["final_response"] = "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다."
        
        return state
    
    async def run_streaming(self, user_input: str, conversation_history: List[BaseMessage] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the agent with streaming updates using LangGraph"""
        if conversation_history is None:
            conversation_history = []
        
        # Initialize MCP if not already done
        await self._ensure_mcp_initialized()
        
        # Initialize state
        state: StreamingAgentState = {
            "messages": conversation_history + [HumanMessage(content=user_input)],
            "user_input": user_input,
            "needs_tools": False,
            "final_response": "",
            "error_message": "",
            "current_step": "",
            "step_details": "",
            "iteration_count": 0
        }
        
        try:
            if not self.graph:
                yield {"type": "error", "message": "Graph not initialized. No tools available."}
                return
            
            # Run the graph with streaming updates
            async for update in self._stream_graph_execution(state):
                yield update
                
        except Exception as e:
            logger.error(f"❌ Error in run_streaming: {e}")
            yield {"type": "error", "message": f"I apologize, but I encountered an error: {str(e)}"}
    
    async def _stream_graph_execution(self, state: StreamingAgentState) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream the execution of the LangGraph with progress updates"""
        try:
            # Step 1: Analyze input
            yield {"type": "step", "message": "🔍 Analyzing your request...", "details": ""}
            await asyncio.sleep(0.3)
            
            # Execute the graph
            final_state = await self.graph.ainvoke(state)
            
            # Extract and stream tool results
            tool_results = self._extract_tool_results(final_state)
            for tool_name, tool_result in tool_results:
                yield {"type": "tool_result", "tool_name": tool_name, "result": tool_result}
                await asyncio.sleep(0.1)
            
            # Stream the final response
            if final_state.get("final_response"):
                response = final_state["final_response"]
                for char in response:
                    yield {"type": "stream", "chunk": char}
                    await asyncio.sleep(0.01)
                
                # Determine if tools were used
                used_tools = final_state.get("needs_tools", False)
                yield {"type": "response_complete", "message": response, "used_tools": used_tools}
            else:
                yield {"type": "error", "message": "No response generated"}
                
        except Exception as e:
            logger.error(f"❌ Error in graph execution: {e}")
            yield {"type": "error", "message": f"Error executing workflow: {str(e)}"}
    
    def _extract_tool_results(self, state: StreamingAgentState) -> List[Tuple[str, str]]:
        """Extract tool results from the conversation state"""
        tool_results = []
        
        for message in state.get("messages", []):
            if hasattr(message, 'content') and message.content:
                # Check if this is a tool result message
                if "tool_result" in str(type(message)) or "ToolMessage" in str(type(message)):
                    # Extract tool name and result
                    tool_name = getattr(message, 'name', 'Unknown Tool')
                    tool_result = message.content
                    tool_results.append((tool_name, tool_result))
        
        return tool_results
    
    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Execute a specific tool"""
        logger.info(f"Attempting to execute tool: {tool_name} with args: {tool_args}")
        
        if not self.tools:
            logger.error("No tools available. MCP servers may not be initialized.")
            return "No tools available. MCP servers may not be initialized."
        
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(tool_args)
                    logger.info(f"Tool {tool_name} executed successfully")
                    return result
                except Exception as e:
                    logger.error(f"Error executing {tool_name}: {str(e)}")
                    return f"Error executing {tool_name}: {str(e)}"
        
        available_tools = [tool.name for tool in self.tools] if self.tools else []
        logger.warning(f"Tool {tool_name} not found. Available tools: {available_tools}")
        return f"Tool {tool_name} not found. Available tools: {available_tools}"
    
    async def close(self):
        """Close the agent and clean up resources"""
        if self._mcp_initialized:
            try:
                await mcp_client.close()
                self._mcp_initialized = False
                logger.info("✅ MCP client closed successfully")
            except Exception as e:
                logger.error(f"Error closing MCP client: {e}")