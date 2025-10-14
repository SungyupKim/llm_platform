from typing import Dict, List, Any, TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from config import Config
from mcp_client import mcp_client
from bedrock_client import bedrock_client
import json

class WorkerState(TypedDict):
    """State for worker agents"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    current_task: str
    available_tools: Dict[str, List[Dict[str, Any]]]
    worker_result: str
    tool_calls: List[Dict[str, Any]]

class BaseWorker:
    """Base class for all worker agents"""
    
    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        
        # Use the fallback Bedrock client for workers
        self.llm = bedrock_client.create_worker_llm()
    
    async def execute_task(self, state: WorkerState) -> WorkerState:
        """Execute the assigned task using available tools"""
        raise NotImplementedError

class FilesystemWorker(BaseWorker):
    """Worker for file system operations"""
    
    def __init__(self):
        super().__init__("filesystem_worker")
        self.system_prompt = """You are a filesystem worker agent. You can perform file operations like:
- Reading files
- Writing files
- Listing directories
- Creating directories
- Deleting files/directories

Use the available filesystem tools to complete the task. Always provide clear feedback about what you're doing."""

    async def execute_task(self, state: WorkerState) -> WorkerState:
        """Execute filesystem-related tasks"""
        task = state["current_task"]
        
        # Get filesystem tools
        filesystem_tools = state["available_tools"].get("filesystem", [])
        
        # Create a simple tools description to avoid JSON formatting issues
        tools_description = "\n".join([f"- {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}" 
                                     for tool in filesystem_tools])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", f"Task: {task}\n\nAvailable tools:\n{tools_description}")
        ])
        
        response = await self.llm.ainvoke(prompt.format_messages())
        print(f"🤖 LLM Response: {response.content}")
        
        # Parse the response to extract tool calls
        tool_calls = []
        
        try:
            # Try to parse as JSON first
            parsed = json.loads(response.content)
            if isinstance(parsed, list):
                tool_calls = parsed
            else:
                tool_calls = [parsed]
        except json.JSONDecodeError:
            # Try to extract JSON from the response content
            import re
            # Look for JSON objects or arrays
            json_patterns = [
                r'\[.*?\]',  # Array pattern
                r'\{.*?\}',  # Object pattern
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response.content, re.DOTALL)
                for match in matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, list):
                            tool_calls.extend(parsed)
                        else:
                            tool_calls.append(parsed)
                        break
                    except json.JSONDecodeError:
                        continue
                if tool_calls:
                    break
        
        # If no valid JSON found, create a default tool call based on task
        if not tool_calls:
            user_message = state["messages"][-1].content.lower() if state["messages"] else ""
            if any(keyword in user_message for keyword in ["list", "ls", "directory", "files"]):
                tool_calls = [{
                    "tool": "list_directory",
                    "arguments": {"path": "."}
                }]
            elif any(keyword in user_message for keyword in ["read", "open", "view"]):
                tool_calls = [{
                    "tool": "read_file",
                    "arguments": {"path": "config.py"}
                }]
            elif any(keyword in user_message for keyword in ["write", "create", "new"]):
                tool_calls = [{
                    "tool": "write_file",
                    "arguments": {"path": "test.txt", "content": "Hello from filesystem worker!"}
                }]
            else:
                tool_calls = [{
                    "tool": "list_directory",
                    "arguments": {"path": "."}
                }]
        
        state["tool_calls"] = tool_calls
        
        # Execute the tool calls
        results = []
        print(f"🔧 Tool calls to execute: {state.get('tool_calls', [])}")
        
        for tool_call in state.get("tool_calls", []):
            try:
                print(f"🔧 Executing tool: {tool_call}")
                result = await mcp_client.call_tool(
                    "filesystem",
                    tool_call.get("tool", "list_directory"),
                    tool_call.get("arguments", {"path": "."})
                )
                results.append(result)
            except Exception as e:
                print(f"❌ Tool execution error: {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "tool": tool_call.get("tool", "unknown")
                })
        
        state["worker_result"] = json.dumps(results, indent=2)
        return state

class SearchWorker(BaseWorker):
    """Worker for web search operations"""
    
    def __init__(self):
        super().__init__("search_worker")
        self.system_prompt = """You are a search worker agent. You can perform web searches to find information.
Use the available search tools to complete the task. Always provide relevant and accurate information."""

    async def execute_task(self, state: WorkerState) -> WorkerState:
        """Execute search-related tasks"""
        task = state["current_task"]
        
        # Get search tools
        search_tools = state["available_tools"].get("brave-search", [])
        
        # Create a simple tools description to avoid JSON formatting issues
        tools_description = "\n".join([f"- {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}" 
                                     for tool in search_tools])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", f"Task: {task}\n\nAvailable tools:\n{tools_description}")
        ])
        
        response = await self.llm.ainvoke(prompt.format_messages())
        print(f"🤖 Search LLM Response: {response.content}")
        
        # Parse the response to extract tool calls
        tool_calls = []
        
        try:
            # Try to parse as JSON first
            parsed = json.loads(response.content)
            if isinstance(parsed, list):
                tool_calls = parsed
            else:
                tool_calls = [parsed]
        except json.JSONDecodeError:
            # Try to extract JSON from the response content
            import re
            json_patterns = [
                r'\[.*?\]',  # Array pattern
                r'\{.*?\}',  # Object pattern
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response.content, re.DOTALL)
                for match in matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, list):
                            tool_calls.extend(parsed)
                        else:
                            tool_calls.append(parsed)
                        break
                    except json.JSONDecodeError:
                        continue
                if tool_calls:
                    break
        
        # If no valid JSON found, create a default search call
        if not tool_calls:
            tool_calls = [{
                "tool": "search",
                "arguments": {"query": task}
            }]
        
        state["tool_calls"] = tool_calls
        
        # Execute the tool calls
        results = []
        print(f"🔍 Search tool calls to execute: {state.get('tool_calls', [])}")
        
        for tool_call in state.get("tool_calls", []):
            try:
                print(f"🔍 Executing search tool: {tool_call}")
                result = await mcp_client.call_tool(
                    "brave-search",
                    tool_call.get("tool", "search"),
                    tool_call.get("arguments", {"query": task})
                )
                results.append(result)
            except Exception as e:
                print(f"❌ Search tool execution error: {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "tool": tool_call.get("tool", "unknown")
                })
        
        state["worker_result"] = json.dumps(results, indent=2)
        return state

class DatabaseWorker(BaseWorker):
    """Worker for database operations"""
    
    def __init__(self):
        super().__init__("database_worker")
        self.system_prompt = """You are a database worker agent. You can perform database operations like:
- Querying data
- Inserting records
- Updating records
- Deleting records
- Creating tables

Use the available database tools to complete the task. Always be careful with data modifications."""

    async def execute_task(self, state: WorkerState) -> WorkerState:
        """Execute database-related tasks"""
        task = state["current_task"]
        
        # Get database tools
        db_tools = state["available_tools"].get("postgres", [])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", f"Task: {task}\n\nAvailable tools: {json.dumps(db_tools, indent=2)}")
        ])
        
        response = await self.llm.ainvoke(prompt.format_messages())
        
        # Parse the response to extract tool calls
        try:
            tool_calls = json.loads(response.content)
            if isinstance(tool_calls, list):
                state["tool_calls"] = tool_calls
            else:
                state["tool_calls"] = [tool_calls]
        except json.JSONDecodeError:
            # If not JSON, create a simple query call
            state["tool_calls"] = [{
                "tool": "query",
                "arguments": {"sql": "SELECT 1"},
                "reasoning": response.content
            }]
        
        # Execute the tool calls
        results = []
        for tool_call in state["tool_calls"]:
            try:
                result = await mcp_client.call_tool(
                    "postgres",
                    tool_call["tool"],
                    tool_call["arguments"]
                )
                results.append(result)
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                    "tool": tool_call["tool"]
                })
        
        state["worker_result"] = json.dumps(results, indent=2)
        return state

class AWSWorker(BaseWorker):
    """Worker for AWS operations"""
    
    def __init__(self):
        super().__init__("aws_worker")
        self.system_prompt = """You are an AWS worker agent. You can perform AWS operations like:
- S3 operations (upload, download, list)
- EC2 operations (start, stop, list instances)
- Lambda operations (invoke, list functions)
- And other AWS services

Use the available AWS tools to complete the task. Always be careful with AWS resources and costs."""

    async def execute_task(self, state: WorkerState) -> WorkerState:
        """Execute AWS-related tasks"""
        task = state["current_task"]
        
        # For now, we'll simulate AWS operations since we don't have AWS MCP server configured
        # In a real implementation, you would have AWS MCP tools available
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", f"Task: {task}\n\nNote: AWS MCP server not configured in this example")
        ])
        
        response = await self.llm.ainvoke(prompt.format_messages())
        
        # Simulate AWS operation result
        state["worker_result"] = f"AWS Worker Response: {response.content}\n\nNote: This is a simulated response. Configure AWS MCP server for real AWS operations."
        return state

# Worker registry
WORKERS = {
    "filesystem_worker": FilesystemWorker(),
    "search_worker": SearchWorker(),
    "database_worker": DatabaseWorker(),
    "aws_worker": AWSWorker()
}

async def execute_worker_task(worker_name: str, state: WorkerState) -> WorkerState:
    """Execute a task using the specified worker"""
    if worker_name not in WORKERS:
        state["worker_result"] = f"Error: Worker '{worker_name}' not found"
        return state
    
    worker = WORKERS[worker_name]
    return await worker.execute_task(state)
