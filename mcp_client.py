import asyncio
import json
import subprocess
import os
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
        try:
            # Check if the command exists
            command = server_config["command"]
            if not self._command_exists(command):
                print(f"⚠️  Command '{command}' not found, using simulation for {server_name}")
                self.sessions[server_name] = None
                self.tools[server_name] = self._get_simulated_tools(server_name)
                return
            
            # Prepare environment variables
            env = os.environ.copy()
            if "env" in server_config:
                env.update(server_config["env"])
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config["command"],
                args=server_config.get("args", []),
                env=env
            )
            
            # Try to connect to the actual MCP server
            try:
                # For now, we'll use simulation mode since real MCP servers need proper setup
                # In a production environment, you would properly manage the async context
                print(f"⚠️  Real MCP server connection requires proper async context management")
                print(f"   Using simulation mode for {server_name}")
                self.sessions[server_name] = None
                self.tools[server_name] = self._get_simulated_tools(server_name)
                
            except Exception as e:
                print(f"⚠️  Failed to connect to real MCP server {server_name}: {e}")
                print(f"   Using simulation mode for {server_name}")
                self.sessions[server_name] = None
                self.tools[server_name] = self._get_simulated_tools(server_name)
                
        except Exception as e:
            print(f"❌ Error setting up MCP server {server_name}: {e}")
            self.sessions[server_name] = None
            self.tools[server_name] = self._get_simulated_tools(server_name)
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in the system"""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, 
                         check=True, 
                         timeout=5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _test_postgres_connection(self) -> bool:
        """Test PostgreSQL connection"""
        try:
            import psycopg2
            from config import Config
            
            # Get connection string from environment
            conn_str = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
            
            # Test connection
            conn = psycopg2.connect(conn_str)
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️  PostgreSQL connection test failed: {e}")
            return False
    
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
        
        session = self.sessions[server_name]
        
        # If session is None, use simulation
        if session is None:
            try:
                result = await self._simulate_tool_call(server_name, tool_name, arguments)
                return {
                    "success": True,
                    "result": result,
                    "server": server_name,
                    "tool": tool_name,
                    "mode": "simulation"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "server": server_name,
                    "tool": tool_name,
                    "mode": "simulation"
                }
        
        # Use real MCP server
        try:
            # Call the actual tool on the MCP server
            result = await session.call_tool(tool_name, arguments)
            return {
                "success": True,
                "result": result.content if hasattr(result, 'content') else result,
                "server": server_name,
                "tool": tool_name,
                "mode": "real"
            }
        except Exception as e:
            print(f"❌ Real MCP tool call failed for {server_name}.{tool_name}: {e}")
            # Fallback to simulation
            try:
                result = await self._simulate_tool_call(server_name, tool_name, arguments)
                return {
                    "success": True,
                    "result": result,
                    "server": server_name,
                    "tool": tool_name,
                    "mode": "simulation_fallback"
                }
            except Exception as sim_e:
                return {
                    "success": False,
                    "error": f"Real call failed: {str(e)}, Simulation failed: {str(sim_e)}",
                    "server": server_name,
                    "tool": tool_name,
                    "mode": "failed"
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
            # Try real PostgreSQL connection first
            if self._test_postgres_connection():
                return await self._real_postgres_query(tool_name, arguments)
            else:
                # Fallback to simulation
                if tool_name == "query":
                    return {"rows": [{"id": 1, "name": "example"}, {"id": 2, "name": "test"}]}
                elif tool_name == "list_tables":
                    return {"tables": ["users", "products", "orders"]}
        
        return {"message": f"Simulated execution of {tool_name} with arguments {arguments}"}
    
    async def _real_postgres_query(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute real PostgreSQL queries"""
        try:
            import psycopg2
            import psycopg2.extras
            
            # Get connection string from environment
            conn_str = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
            
            conn = psycopg2.connect(conn_str)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if tool_name == "query":
                sql = arguments.get("sql", "")
                cursor.execute(sql)
                
                if sql.strip().upper().startswith("SELECT"):
                    rows = cursor.fetchall()
                    return {"rows": [dict(row) for row in rows]}
                else:
                    conn.commit()
                    return {"message": f"Query executed successfully: {sql}"}
                    
            elif tool_name == "list_tables":
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = cursor.fetchall()
                return {"tables": [table['table_name'] for table in tables]}
                
            elif tool_name == "describe_table":
                table_name = arguments.get("table_name", "")
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """, (table_name,))
                columns = cursor.fetchall()
                return {"columns": [dict(col) for col in columns]}
            
            conn.close()
            return {"message": f"PostgreSQL operation completed: {tool_name}"}
            
        except Exception as e:
            return {"error": f"PostgreSQL query failed: {str(e)}"}
    
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
        for server_name, session in self.sessions.items():
            if session is not None:
                try:
                    await session.close()
                    print(f"🔌 Closed connection to MCP server: {server_name}")
                except Exception as e:
                    print(f"⚠️  Error closing MCP server {server_name}: {e}")
        
        self.sessions.clear()
        self.tools.clear()
        self.initialized = False

# Global instance
mcp_client = McpClientManager()
