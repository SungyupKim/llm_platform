from typing import Dict, List, Any, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from bedrock_client import bedrock_client
from mcp_client import mcp_client
from config import Config
import json

class ToolAgentState(TypedDict):
    """State for the tool agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    user_input: str
    needs_tools: bool
    final_response: str
    error_message: str

# Define tools using LangChain's @tool decorator
@tool
async def list_directory(path: str = ".") -> str:
    """List files and directories in the specified path"""
    try:
        result = await mcp_client.call_tool("filesystem", "list_directory", {"path": path})
        if result["success"]:
            return json.dumps(result["result"], indent=2)
        else:
            return f"Error: {result['error']}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

@tool
async def read_file(path: str) -> str:
    """Read the contents of a file"""
    try:
        result = await mcp_client.call_tool("filesystem", "read_file", {"path": path})
        if result["success"]:
            return result["result"].get("content", "File is empty")
        else:
            return f"Error: {result['error']}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
async def write_file(path: str, content: str) -> str:
    """Write content to a file"""
    try:
        result = await mcp_client.call_tool("filesystem", "write_file", {"path": path, "content": content})
        if result["success"]:
            return result["result"].get("message", "File written successfully")
        else:
            return f"Error: {result['error']}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

@tool
async def search_web(query: str) -> str:
    """Search the web using Brave Search"""
    try:
        result = await mcp_client.call_tool("brave-search", "search", {"query": query})
        if result["success"]:
            return json.dumps(result["result"], indent=2)
        else:
            return f"Error: {result['error']}"
    except Exception as e:
        return f"Error searching web: {str(e)}"

@tool
async def query_database(sql: str) -> str:
    """Execute a SQL query on the database"""
    try:
        result = await mcp_client.call_tool("postgres", "query", {"sql": sql})
        if result["success"]:
            return json.dumps(result["result"], indent=2)
        else:
            return f"Error: {result['error']}"
    except Exception as e:
        return f"Error querying database: {str(e)}"

@tool
async def list_database_tables() -> str:
    """List all tables in the database"""
    try:
        result = await mcp_client.call_tool("postgres", "list_tables", {})
        if result["success"]:
            return json.dumps(result["result"], indent=2)
        else:
            return f"Error: {result['error']}"
    except Exception as e:
        return f"Error listing tables: {str(e)}"

@tool
async def describe_table(table_name: str) -> str:
    """Get the schema of a specific table"""
    try:
        result = await mcp_client.call_tool("postgres", "describe_table", {"table_name": table_name})
        if result["success"]:
            return json.dumps(result["result"], indent=2)
        else:
            return f"Error: {result['error']}"
    except Exception as e:
        return f"Error describing table: {str(e)}"

class LangChainToolAgent:
    """LangChain ToolNode를 사용하는 에이전트"""
    
    def __init__(self):
        self.llm = bedrock_client.get_llm()
        
        # Define available tools
        self.tools = [
            list_directory,
            read_file,
            write_file,
            search_web,
            query_database,
            list_database_tables,
            describe_table
        ]
        
        # Create ToolNode
        self.tool_node = ToolNode(self.tools)
        
        # Wrap ToolNode with debugging
        self._original_tool_node = self.tool_node
        self.tool_node = self._debug_tool_node
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with ToolNode"""
        
        workflow = StateGraph(ToolAgentState)
        
        # Add nodes
        workflow.add_node("analyze_input", self._analyze_input_node)
        workflow.add_node("direct_response", self._direct_response_node)
        workflow.add_node("llm_with_tools", self._llm_with_tools_node)
        workflow.add_node("tools", self.tool_node)
        workflow.add_node("synthesize_response", self._synthesize_response_node)
        
        # Add edges
        workflow.set_entry_point("analyze_input")
        
        # Conditional edge: decide whether to use tools or respond directly
        workflow.add_conditional_edges(
            "analyze_input",
            self._should_use_tools,
            {
                "direct": "direct_response",
                "tools": "llm_with_tools"
            }
        )
        
        workflow.add_edge("direct_response", END)
        
        # From LLM with tools, check if tools are needed
        workflow.add_conditional_edges(
            "llm_with_tools",
            self._should_continue_with_tools,
            {
                "tools": "tools",
                "synthesize": "synthesize_response"
            }
        )
        
        # From tools back to LLM for synthesis
        workflow.add_edge("tools", "synthesize_response")
        workflow.add_edge("synthesize_response", END)
        
        return workflow.compile()
    
    async def _analyze_input_node(self, state: ToolAgentState) -> ToolAgentState:
        """Analyze user input to determine if tools are needed"""
        user_input = state["user_input"]
        
        # Simple keyword-based analysis
        user_lower = user_input.lower()
        needs_tools = any(keyword in user_lower for keyword in [
            "list", "ls", "directory", "files", "read", "write", "create", "search", "find", "query", "database", "sql", 
            "table", "describe", "structure", "schema", "employee", "select", "show", "display"
        ])
        
        state["needs_tools"] = needs_tools
        return state
    
    async def _direct_response_node(self, state: ToolAgentState) -> ToolAgentState:
        """Generate direct response without tools"""
        user_input = state["user_input"]
        conversation_history = state["messages"][:-1]  # Exclude the current user message
        
        # Create conversation context
        context_messages = []
        for msg in conversation_history[-6:]:  # Keep last 6 messages for context
            if isinstance(msg, HumanMessage):
                context_messages.append(("human", msg.content))
            elif isinstance(msg, AIMessage):
                context_messages.append(("assistant", msg.content))
        
        # Add current user message
        context_messages.append(("human", user_input))
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful AI assistant. Provide clear, accurate, and helpful responses to user questions and requests. 
            
Be conversational, friendly, and informative."""),
            *context_messages
        ])
        
        try:
            response = await self.llm.ainvoke(prompt.format_messages())
            state["final_response"] = response.content
        except Exception as e:
            state["final_response"] = f"I apologize, but I encountered an error while processing your request: {str(e)}"
        
        return state
    
    async def _llm_with_tools_node(self, state: ToolAgentState) -> ToolAgentState:
        """LLM node with tools available"""
        try:
            # Initialize MCP client
            await mcp_client.initialize()
            
            print(f"🔍 LLM with tools - messages: {len(state['messages'])}")
            print(f"🔍 Last message: {state['messages'][-1].content if state['messages'] else 'None'}")
            
            # Get LLM response with tools
            response = await self.llm_with_tools.ainvoke(state["messages"])
            
            print(f"🔍 LLM response: {response.content}")
            print(f"🔍 Has tool calls: {hasattr(response, 'tool_calls') and response.tool_calls}")
            if hasattr(response, 'tool_calls') and response.tool_calls:
                print(f"🔍 Tool calls: {response.tool_calls}")
            
            # Add the response to messages
            state["messages"].append(response)
            
        except Exception as e:
            print(f"❌ LLM with tools error: {e}")
            import traceback
            traceback.print_exc()
            state["error_message"] = f"LLM with tools failed: {str(e)}"
        
        return state
    
    async def _synthesize_response_node(self, state: ToolAgentState) -> ToolAgentState:
        """Synthesize final response"""
        try:
            print(f"🔍 Synthesize - messages count: {len(state['messages'])}")
            for i, msg in enumerate(state["messages"]):
                print(f"🔍 Message {i}: {type(msg).__name__} - {msg.content[:100]}...")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    print(f"🔍 Message {i} tool calls: {msg.tool_calls}")
            
            # Get the last message (should be from LLM after tool execution)
            if state["messages"]:
                last_message = state["messages"][-1]
                if isinstance(last_message, AIMessage):
                    state["final_response"] = last_message.content
                elif hasattr(last_message, 'content') and 'ToolMessage' in str(type(last_message)):
                    # This is a tool result, format it nicely
                    state["final_response"] = f"Tool execution result:\n{last_message.content}"
                else:
                    state["final_response"] = "Task completed successfully."
            else:
                state["final_response"] = "Task completed successfully."
                
        except Exception as e:
            print(f"❌ Synthesize error: {e}")
            state["final_response"] = f"Error synthesizing response: {str(e)}"
        
        return state
    
    def _should_use_tools(self, state: ToolAgentState) -> Literal["direct", "tools"]:
        """Determine whether to use tools or respond directly"""
        if state.get("error_message"):
            return "direct"  # Fallback to direct response on error
        
        return "tools" if state.get("needs_tools", False) else "direct"
    
    def _should_continue_with_tools(self, state: ToolAgentState) -> Literal["tools", "synthesize"]:
        """Determine whether to use tools or synthesize response"""
        if state.get("error_message"):
            print("🔍 Should continue: error detected, synthesizing")
            return "synthesize"  # End on error
        
        # Check if the last message has tool calls
        if state["messages"]:
            last_message = state["messages"][-1]
            print(f"🔍 Last message type: {type(last_message)}")
            print(f"🔍 Is AIMessage: {isinstance(last_message, AIMessage)}")
            print(f"🔍 Has tool_calls attr: {hasattr(last_message, 'tool_calls')}")
            if hasattr(last_message, 'tool_calls'):
                print(f"🔍 Tool calls: {last_message.tool_calls}")
            
            if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                print("🔍 Should continue: tool calls detected, going to tools")
                return "tools"
        
        print("🔍 Should continue: no tool calls, synthesizing")
        return "synthesize"
    
    async def _debug_tool_node(self, state: ToolAgentState) -> ToolAgentState:
        """Debug wrapper for ToolNode"""
        print("🔧 ToolNode called!")
        print(f"🔧 State messages: {len(state['messages'])}")
        if state["messages"]:
            last_message = state["messages"][-1]
            print(f"🔧 Last message: {last_message}")
            if hasattr(last_message, 'tool_calls'):
                print(f"🔧 Tool calls: {last_message.tool_calls}")
        
        try:
            result = await self._original_tool_node.ainvoke(state)
            print("🔧 ToolNode completed successfully")
            return result
        except Exception as e:
            print(f"❌ ToolNode error: {e}")
            import traceback
            traceback.print_exc()
            state["error_message"] = f"ToolNode failed: {str(e)}"
            return state
    
    async def run(self, user_input: str, conversation_history: List[BaseMessage] = None) -> Dict[str, Any]:
        """Run the tool agent with user input"""
        if conversation_history is None:
            conversation_history = []
        
        # Initialize state
        initial_state: ToolAgentState = {
            "messages": conversation_history + [HumanMessage(content=user_input)],
            "user_input": user_input,
            "needs_tools": False,
            "final_response": "",
            "error_message": ""
        }
        
        try:
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Add the final response to messages
            if final_state["final_response"]:
                final_state["messages"].append(AIMessage(content=final_state["final_response"]))
            
            return {
                "success": not bool(final_state.get("error_message")),
                "response": final_state["final_response"],
                "messages": final_state["messages"],
                "used_tools": len(final_state["messages"]) > len(initial_state["messages"]),
                "error": final_state.get("error_message", "")
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error: {str(e)}",
                "messages": conversation_history + [HumanMessage(content=user_input)],
                "used_tools": False,
                "error": f"Agent execution failed: {str(e)}"
            }
        finally:
            # Clean up MCP connections
            try:
                await mcp_client.close()
            except:
                pass
    
    async def close(self):
        """Close the agent and clean up resources"""
        await mcp_client.close()
