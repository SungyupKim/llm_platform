"""
Streaming LLM Agent with MCP tool support using LangGraph
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, AsyncGenerator, Literal, Tuple
from typing_extensions import TypedDict, Annotated

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from bedrock_client import bedrock_client
from mcp_client import mcp_client

# Configure logger for streaming agent
logger = logging.getLogger(__name__)

class StreamingAgentState(TypedDict):
    """State for the streaming agent"""
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    final_response: str
    error_message: str
    iteration_count: int
    needs_tools: bool

class StreamingAgent:
    """Streaming LLM Agent with MCP tool support"""
    
    def __init__(self):
        self.llm = bedrock_client.get_llm()
        self.tools = None
        self.tool_node = None
        self.llm_with_tools = None
        self.graph = None
        self._mcp_initialized = False
    
    async def _ensure_mcp_initialized(self):
        """Ensure MCP client is initialized and tools are loaded"""
        if not self._mcp_initialized:
            logger.info("🚀 Initializing MCP client for the first time...")
            await mcp_client.initialize()
            await self._load_mcp_tools()
            self._mcp_initialized = True
            logger.info("✅ MCP initialization completed")
    
    async def _load_mcp_tools(self):
        """Load tools from MCP servers and convert to LangChain tools"""
        try:
            mcp_tools = await mcp_client.get_available_tools()
            logger.info(f"🔍 MCP tools received: {mcp_tools}")
            
            self.tools = []
            for server_name, server_tools in mcp_tools.items():
                logger.info(f"🔍 Processing server: {server_name} with {len(server_tools)} tools")
                for tool_info in server_tools:
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
                self._build_graph()
            else:
                logger.warning("⚠️  No tools loaded from MCP servers")
                
        except Exception as e:
            logger.error(f"❌ Error loading MCP tools: {e}")
            self.tools = []
    
    def _create_langchain_tool(self, tool_info: Dict[str, Any], server_name: str):
        """Convert MCP tool info to LangChain tool"""
        try:
            tool_name = tool_info["name"]
            tool_description = tool_info["description"]
            tool_input_schema = tool_info.get("inputSchema", {})
            
            # Create dynamic Pydantic model for tool input
            from pydantic import BaseModel, Field, create_model
            
            # Extract properties from input schema
            properties = tool_input_schema.get("properties", {})
            required_fields = tool_input_schema.get("required", [])
            
            # Create field definitions
            field_definitions = {}
            for field_name, field_info in properties.items():
                field_description = field_info.get("description", "")
                
                # Add default values for common tools
                if tool_name == "list_directory" and field_name == "path":
                    field_definitions[field_name] = (str, Field(default=".", description=field_description))
                elif tool_name == "read_file" and field_name == "path":
                    field_definitions[field_name] = (str, Field(default="README.md", description=field_description))
                elif tool_name == "query":
                    # PostgreSQL MCP expects 'sql' parameter
                    if field_name == "sql":
                        field_definitions[field_name] = (str, Field(description=field_description))
                    else:
                        field_definitions[field_name] = (str, Field(description=field_description))
                else:
                    if field_name in required_fields:
                        field_definitions[field_name] = (str, Field(description=field_description))
                    else:
                        field_definitions[field_name] = (str, Field(default="", description=field_description))
            
            # Create the Pydantic model
            ToolInput = create_model(f"{tool_name}Input", **field_definitions)
            
            # Create a dynamic tool function
            async def tool_func(**kwargs) -> str:
                try:
                    logger.info(f"🔍 tool_func called for {tool_name} with kwargs: {kwargs}")
                    
                    # Handle special case for query tool - PostgreSQL MCP expects 'sql' parameter
                    if tool_name == "query" and "sql" in kwargs:
                        logger.info(f"🔍 Using sql parameter for query tool: {kwargs}")
                    elif tool_name == "query" and "query" in kwargs:
                        # If 'query' parameter is passed, convert to 'sql' for PostgreSQL MCP
                        new_kwargs = {"sql": kwargs["query"]}
                        for key, value in kwargs.items():
                            if key != "query":
                                new_kwargs[key] = value
                        kwargs = new_kwargs
                        logger.info(f"🔍 Converted query to sql parameter: {kwargs}")
                    
                    logger.info(f"🔍 Executing tool {tool_name} on server {server_name} with args: {kwargs}")
                    result = await mcp_client.call_tool(server_name, tool_name, kwargs)
                    logger.info(f"🔍 Tool result: {result}")
                    if result["success"]:
                        return json.dumps(result["result"], indent=2)
                    else:
                        return f"Error: {result['error']}"
                except Exception as e:
                                logger.error(f"❌ Error executing {tool_name}: {str(e)}")
                                return f"Error executing {tool_name}: {str(e)}"
            
            # Create LangChain tool
            from langchain_core.tools import tool
            
            langchain_tool = tool(
                name=tool_name,
                description=tool_description,
                args_schema=ToolInput,
                func=tool_func
            )
            
            return langchain_tool
            
        except Exception as e:
                logger.error(f"❌ Error creating LangChain tool {tool_info.get('name', 'unknown')}: {e}")
                return None
        
    def _build_graph(self):
        """Build the LangGraph workflow"""
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
        
        workflow.add_conditional_edges(
            "execute_tools",
            self._should_continue_after_tools,
            {
                "continue": "llm_with_tools",
                "final": "final_response"
            }
        )
        
        workflow.add_edge("direct_response", END)
        workflow.add_edge("final_response", END)
        
        # Compile the graph
        self.graph = workflow.compile()
        logger.info("✅ LangGraph workflow built successfully")
    
    def _should_use_tools(self, state: StreamingAgentState) -> Literal["direct", "tools"]:
        """Determine if tools should be used based on analysis"""
        needs_tools = state.get("needs_tools", False)
        logger.info(f"🔍 _should_use_tools: needs_tools = {needs_tools}, state keys = {list(state.keys())}")
        result = "tools" if needs_tools else "direct"
        logger.info(f"🔍 _should_use_tools: returning {result}")
        return result
    
    def _should_execute_tools(self, state: StreamingAgentState) -> Literal["execute", "final"]:
        """Determine if tools should be executed"""
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "execute"
        else:
            if last_message.content and not state.get("final_response"):
                state["final_response"] = last_message.content
                logger.info("✅ Final response set from LLM with tools")
            return "final"
    
    def _should_continue_after_tools(self, state: StreamingAgentState) -> Literal["continue", "final"]:
        """Determine if we should continue after tool execution"""
        iteration_count = state.get("iteration_count", 0)
        max_iterations = 5
        
        if iteration_count >= max_iterations:
            logger.info(f"🔄 Max iterations reached ({max_iterations}), ending workflow")
            return "final"
        
        last_message = state["messages"][-1]
        if hasattr(last_message, 'content') and last_message.content:
            return "final"
        
        return "continue"
    
    async def _analyze_input_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """Analyze input to determine if tools are needed"""
        logger.info("🔍 Analyzing input to determine tool usage...")
        
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that analyzes user requests to determine if tools are needed.

Available tools: {tool_names}

Analyze the user's request and determine if any tools are needed to fulfill it.
Respond with "YES" if tools are needed, "NO" if a direct response is sufficient.

Focus on the PRIMARY intent of the user's request:

Database-related requests (use query tool):
- "데이터베이스 목록", "database list", "show databases" -> YES
- "테이블 목록", "table list", "show tables" -> YES
- "데이터베이스 정보" -> YES

File system requests (use filesystem tools):
- "디렉토리 목록", "list directory", "파일 목록" -> YES
- "파일 읽기", "read file" -> YES

Web search requests (use search tools):
- "검색", "search", "웹 검색" -> YES

General conversation (no tools needed):
- "Hello", "안녕", "How are you?" -> NO
- "What is the weather?" -> NO
- "Explain something" -> NO
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
            logger.info(f"🔍 State after analysis: {dict(state)}")
            
        except Exception as e:
            logger.error(f"❌ Error analyzing input: {e}")
            state["needs_tools"] = False
        
        logger.info(f"🔍 Returning state from _analyze_input_node: needs_tools = {state.get('needs_tools')}")
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
            ("system", "You are a helpful AI assistant. Provide clear, accurate, and helpful responses."),
                *context_messages
            ])
                
            response = await self.llm.ainvoke(prompt.format_messages())
            state["messages"].append(response)
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
            # Add system message to help with tool usage
            system_message = SystemMessage(content="""You are a helpful AI assistant with access to various tools. When using tools, be precise and only use the most relevant tool for the user's request:

1. For database-related requests (query tool):
   - "데이터베이스 목록", "database list", "show databases" → Use query tool with "SELECT datname FROM pg_database;"
   - "테이블 목록", "table list", "show tables" → Use query tool with "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
   - Table structure requests → Use query tool with appropriate SQL

2. For file system requests:
   - "디렉토리 목록", "list directory", "파일 목록" → Use list_directory tool
   - "파일 읽기", "read file" → Use read_file tool

3. For web search requests:
   - "검색", "search", "웹 검색" → Use web search tools

IMPORTANT: Only use ONE tool at a time. Do not use multiple tools unless the user explicitly asks for multiple different types of information. Focus on the primary request.""")
            
            # Prepend system message to the conversation
            messages_with_system = [system_message] + state["messages"]
            response = await self.llm_with_tools.ainvoke(messages_with_system)
            state["messages"].append(response)
            
            # If no tool calls, set final response
            if not (hasattr(response, 'tool_calls') and response.tool_calls):
                state["final_response"] = response.content
                logger.info("✅ Final response set from LLM with tools (no tool calls)")
            
        except Exception as e:
            logger.error(f"❌ Error in LLM with tools: {e}")
            state["error_message"] = str(e)
        
        return state
    
    async def _execute_tools_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """Execute tools using ToolNode"""
        logger.info("🔧 Executing tools...")
        
        try:
            # Use ToolNode to execute tools
            tool_result = await self.tool_node.ainvoke(state)
            state["messages"].extend(tool_result["messages"])
            
        except Exception as e:
            logger.error(f"❌ Error executing tools: {e}")
            state["error_message"] = str(e)
        
        return state
    
    async def _final_response_node(self, state: StreamingAgentState) -> StreamingAgentState:
        """Generate final response"""
        logger.info("📝 Generating final response...")
        
        try:
            if not state.get("final_response"):
                # Generate a final response based on the conversation
                response = await self.llm.ainvoke(state["messages"])
                state["final_response"] = response.content
                state["messages"].append(response)
            
        except Exception as e:
            logger.error(f"❌ Error in final response: {e}")
            state["error_message"] = str(e)
        
        return state
    
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
    
    async def _stream_graph_execution(self, initial_state: StreamingAgentState) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream the graph execution"""
        try:
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Stream tool results if any
            tool_results = self._extract_tool_results(final_state)
            for tool_name, result in tool_results:
                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": result
                }
            
            # Stream the final response
            final_response = final_state.get("final_response", "")
            if final_response:
                # Stream the response character by character
                for char in final_response:
                    yield {"type": "stream", "chunk": char}
                    await asyncio.sleep(0.01)  # Small delay for streaming effect
                
                yield {"type": "response_complete", "message": final_response, "used_tools": len(tool_results) > 0}
            else:
                yield {"type": "response_complete", "message": "No response generated", "used_tools": False}
                
        except Exception as e:
            logger.error(f"❌ Error in graph execution: {e}")
            yield {"type": "error", "message": str(e)}
    
    async def run_streaming(self, user_input: str, history: List[BaseMessage] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the streaming agent with the given input"""
        try:
            # Ensure MCP is initialized
            await self._ensure_mcp_initialized()
            
            if not self.tools or not self.llm_with_tools:
                logger.warning("⚠️  No tools available, falling back to direct response")
                yield {"type": "step", "message": "No tools available, generating direct response..."}
                
                # Generate direct response
                response = await self.llm.ainvoke([HumanMessage(content=user_input)])
                yield {"type": "stream", "chunk": response.content}
                yield {"type": "response_complete", "message": response.content, "used_tools": False}
                return
            
            # Initialize state
            initial_state = StreamingAgentState(
                messages=history or [HumanMessage(content=user_input)],
                user_input=user_input,
                final_response="",
                error_message="",
                iteration_count=0,
                needs_tools=False
            )
            
            # Run the graph
            yield {"type": "step", "message": "Starting agent workflow..."}
            
            async for update in self._stream_graph_execution(initial_state):
                yield update
            
        except Exception as e:
            logger.error(f"❌ Error in run_streaming: {e}")
            yield {"type": "error", "message": str(e)}
    
    async def close(self):
        """Close the agent and clean up resources"""
        try:
            if self._mcp_initialized:
                await mcp_client.close()
                logger.info("✅ MCP client closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing MCP client: {e}")
