import asyncio
import json
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import Config

class McpClientManager:
    """Manager for multiple MCP servers with additional functionality"""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[Dict[str, Any]]] = {}
        self.initialized = False
    
    async def initialize(self):
        """Initialize all MCP servers"""
        if self.initialized:
            return
            
        for server_name, server_config in Config.MCP_SERVERS.items():
            try:
                await self._connect_server(server_name, server_config)
                print(f"✅ Connected to MCP server: {server_name}")
            except Exception as e:
                print(f"❌ Failed to connect to MCP server {server_name}: {e}")
        
        self.initialized = True
        print(f"🚀 McpClientManager initialized with {len(self.sessions)} servers")
    
    async def _connect_server(self, server_name: str, server_config: Dict[str, Any]):
        """Connect to a single MCP server"""
        server_params = StdioServerParameters(
            command=server_config["command"],
            args=server_config.get("args", []),
            env=server_config.get("env", {})
        )
        
        # Note: In a real implementation, you'd need to keep the sessions alive
        # For now, we'll simulate the connection and tools
        self.sessions[server_name] = None  # Placeholder
        self.tools[server_name] = self._get_simulated_tools(server_name)
    
    def _get_simulated_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Get simulated tools for each server type"""
        if server_name == "filesystem":
            return [
                {"name": "read_file", "description": "Read contents of a file"},
                {"name": "write_file", "description": "Write content to a file"},
                {"name": "list_directory", "description": "List files in a directory"},
                {"name": "create_directory", "description": "Create a new directory"}
            ]
        elif server_name == "brave-search":
            return [
                {"name": "search", "description": "Search the web using Brave Search API"},
                {"name": "search_news", "description": "Search for news articles"}
            ]
        elif server_name == "postgres":
            return [
                {"name": "query", "description": "Execute SQL query"},
                {"name": "list_tables", "description": "List all tables in the database"},
                {"name": "describe_table", "description": "Get table schema"}
            ]
        else:
            return []
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific MCP server"""
        if not self.initialized:
            raise RuntimeError("McpClientManager not initialized")
        
        if server_name not in self.sessions:
            return {
                "success": False,
                "error": f"Server {server_name} not connected",
                "server": server_name,
                "tool": tool_name
            }
        
        try:
            # Simulate tool execution for demo purposes
            result = await self._simulate_tool_call(server_name, tool_name, arguments)
            return {
                "success": True,
                "result": result,
                "server": server_name,
                "tool": tool_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "server": server_name,
                "tool": tool_name
            }
    
    async def _simulate_tool_call(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate tool calls for demo purposes"""
        if server_name == "filesystem":
            if tool_name == "read_file":
                return {"content": f"Simulated content of {arguments.get('path', 'file')}"}
            elif tool_name == "list_directory":
                return {"files": ["file1.txt", "file2.py", "directory1/"]}
            elif tool_name == "write_file":
                return {"message": f"Successfully wrote to {arguments.get('path', 'file')}"}
            elif tool_name == "create_directory":
                return {"message": f"Successfully created directory {arguments.get('path', 'directory')}"}
        
        elif server_name == "brave-search":
            if tool_name == "search":
                return {
                    "results": [
                        {"title": "Search Result 1", "url": "https://example1.com", "snippet": "Relevant content..."},
                        {"title": "Search Result 2", "url": "https://example2.com", "snippet": "More relevant content..."}
                    ]
                }
        
        elif server_name == "postgres":
            if tool_name == "query":
                return {"rows": [{"id": 1, "name": "example"}, {"id": 2, "name": "test"}]}
            elif tool_name == "list_tables":
                return {"tables": ["users", "products", "orders"]}
        
        return {"message": f"Simulated execution of {tool_name} with arguments {arguments}"}
    
    async def get_available_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available tools from all servers"""
        if not self.initialized:
            return {}
        return self.tools
    
    async def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Find a tool by name across all servers"""
        tools = await self.get_available_tools()
        for server_name, server_tools in tools.items():
            for tool in server_tools:
                if tool["name"] == tool_name:
                    return {
                        "tool": tool,
                        "server": server_name
                    }
        return None
    
    async def list_servers(self) -> List[str]:
        """List all connected server names"""
        if not self.initialized:
            return []
        return list(self.sessions.keys())
    
    async def close(self):
        """Close all MCP server connections"""
        self.sessions.clear()
        self.tools.clear()
        self.initialized = False

# Global instance
mcp_client = McpClientManager()
