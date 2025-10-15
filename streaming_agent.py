from typing import Dict, List, Any, TypedDict, Annotated, Literal, AsyncGenerator
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

class StreamingAgentState(TypedDict):
    """State for the streaming agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    user_input: str
    needs_tools: bool
    final_response: str
    error_message: str
    current_step: str
    step_details: str

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

class StreamingAgent:
    """Streaming-enabled agent with real-time progress updates"""
    
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
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
    
    async def run_streaming(self, user_input: str, conversation_history: List[BaseMessage] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the agent with streaming updates"""
        if conversation_history is None:
            conversation_history = []
        
        # Initialize state
        state: StreamingAgentState = {
            "messages": conversation_history + [HumanMessage(content=user_input)],
            "user_input": user_input,
            "needs_tools": False,
            "final_response": "",
            "error_message": "",
            "current_step": "",
            "step_details": ""
        }
        
        try:
            # Step 1: Analyze input
            yield {"type": "step", "message": "🔍 Analyzing your request...", "details": ""}
            await asyncio.sleep(0.3)
            
            user_lower = user_input.lower()
            needs_tools = any(keyword in user_lower for keyword in [
                "list", "ls", "directory", "files", "read", "write", "create", "search", "find", "query", "database", "sql", 
                "table", "describe", "structure", "schema", "employee", "select", "show", "display"
            ])
            
            state["needs_tools"] = needs_tools
            
            if not needs_tools:
                # Direct response with character streaming
                yield {"type": "step", "message": "💬 Generating response...", "details": ""}
                await asyncio.sleep(0.2)
                
                conversation_history = state["messages"][:-1]
                context_messages = []
                for msg in conversation_history[-6:]:
                    if isinstance(msg, HumanMessage):
                        context_messages.append(("human", msg.content))
                    elif isinstance(msg, AIMessage):
                        context_messages.append(("assistant", msg.content))
                
                context_messages.append(("human", user_input))
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful AI assistant. Provide clear, accurate, and helpful responses to user questions and requests. 
                    
Be conversational, friendly, and informative. When users ask for multiple tasks, you can use multiple tools in sequence to complete them all."""),
                    *context_messages
                ])
                
                # Stream the response character by character
                full_response = ""
                async for chunk in self.llm.astream(prompt.format_messages()):
                    if hasattr(chunk, 'content') and chunk.content:
                        full_response += chunk.content
                        yield {"type": "stream", "chunk": chunk.content}
                
                state["final_response"] = full_response
                yield {"type": "response_complete", "message": full_response, "used_tools": False}
                return
            
            # Step 2: Initialize MCP client
            yield {"type": "step", "message": "🔧 Initializing tools...", "details": "Connecting to MCP servers"}
            await asyncio.sleep(0.5)
            
            await mcp_client.initialize()
            
            # Step 3: Get LLM response with tools
            yield {"type": "step", "message": "🤖 AI is thinking...", "details": "Analyzing request and selecting tools"}
            await asyncio.sleep(0.3)
            
            # Get LLM response with tools
            response = await self.llm_with_tools.ainvoke(state["messages"])
            
            # Stream the response content if it exists
            if hasattr(response, 'content') and response.content:
                for char in response.content:
                    yield {"type": "stream", "chunk": char}
                    await asyncio.sleep(0.01)  # Small delay for typing effect
            
            yield {"type": "step", "message": "🧠 AI decided to use tools", "details": f"Response: {response.content[:100]}..."}
            await asyncio.sleep(0.3)
            
            # Add the response to messages
            state["messages"].append(response)
            
            # Step 4: Check if tools are needed
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_count = len(response.tool_calls)
                yield {"type": "step", "message": "🔧 Executing tools...", "details": f"Running {tool_count} tool(s)"}
                await asyncio.sleep(0.3)
                
                # Execute tools and get LLM interpretation
                all_tool_results = []
                for i, tool_call in enumerate(response.tool_calls):
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    yield {"type": "step", "message": f"⚙️ Running {tool_name}...", "details": f"Arguments: {json.dumps(tool_args, indent=2)}"}
                    await asyncio.sleep(0.2)
                    
                    # Execute the tool
                    tool_result = await self._execute_tool(tool_name, tool_args)
                    # Store raw result for LLM interpretation
                    all_tool_results.append({
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "result": tool_result
                    })
                    
                    yield {"type": "step", "message": f"✅ {tool_name} completed", "details": "Analyzing results..."}
                    await asyncio.sleep(0.2)
                
                # Get LLM interpretation of all tool results
                yield {"type": "step", "message": "🧠 Analyzing results...", "details": "Generating user-friendly explanation"}
                await asyncio.sleep(0.3)
                
                # Create a simple interpretation
                interpretation_response = ""
                
                # Simple interpretation based on tool results
                for tool_data in all_tool_results:
                    tool_name = tool_data['tool_name']
                    tool_result = tool_data['result']
                    
                    if tool_name == "list_database_tables":
                        # Parse the JSON result
                        try:
                            result_data = json.loads(tool_result)
                            tables = result_data.get('tables', [])
                            if tables:
                                interpretation_response += f"I found {len(tables)} table(s) in your database:\n"
                                for table in tables:
                                    interpretation_response += f"• {table}\n"
                            else:
                                interpretation_response += "Your database doesn't have any tables yet.\n"
                        except:
                            interpretation_response += f"Database tables: {tool_result}\n"
                    
                    elif tool_name == "describe_table":
                        try:
                            result_data = json.loads(tool_result)
                            columns = result_data.get('columns', [])
                            if columns:
                                interpretation_response += f"The table has {len(columns)} column(s):\n"
                                for col in columns:
                                    col_name = col.get('column_name', 'Unknown')
                                    col_type = col.get('data_type', 'Unknown')
                                    nullable = col.get('is_nullable', 'Unknown')
                                    interpretation_response += f"• {col_name} ({col_type}) - {'Nullable' if nullable == 'YES' else 'Not Null'}\n"
                            else:
                                interpretation_response += f"Table structure: {tool_result}\n"
                        except:
                            interpretation_response += f"Table structure: {tool_result}\n"
                    
                    elif tool_name == "list_directory":
                        try:
                            result_data = json.loads(tool_result)
                            files = result_data.get('files', [])
                            if files:
                                interpretation_response += f"I found {len(files)} item(s) in the directory:\n"
                                for file in files:
                                    interpretation_response += f"• {file}\n"
                            else:
                                interpretation_response += "The directory is empty.\n"
                        except:
                            interpretation_response += f"Directory contents: {tool_result}\n"
                    
                    else:
                        interpretation_response += f"Result from {tool_name}: {tool_result}\n"
                
                # Stream the interpretation
                for char in interpretation_response:
                    yield {"type": "stream", "chunk": char}
                    await asyncio.sleep(0.01)
                
                state["final_response"] = interpretation_response
                yield {"type": "response_complete", "message": interpretation_response, "used_tools": True}
            else:
                yield {"type": "response", "message": response.content, "used_tools": False}
            
        except Exception as e:
            yield {"type": "error", "message": f"I apologize, but I encountered an error: {str(e)}"}
        finally:
            # Clean up MCP connections
            try:
                await mcp_client.close()
            except:
                pass
    
    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Execute a specific tool"""
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(tool_args)
                    return result
                except Exception as e:
                    return f"Error executing {tool_name}: {str(e)}"
        return f"Tool {tool_name} not found"
    
    async def close(self):
        """Close the agent and clean up resources"""
        await mcp_client.close()
