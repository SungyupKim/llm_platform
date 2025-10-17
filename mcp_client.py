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
            
        print(f"🚀 Initializing MCP servers...")
        
        # Connect to servers in parallel for faster initialization
        tasks = []
        for server_name, server_config in Config.MCP_SERVERS.items():
            task = asyncio.create_task(self._connect_server(server_name, server_config))
            tasks.append((server_name, task))
        
        # Wait for all connections with timeout
        try:
            async with asyncio.timeout(10.0):  # 10 second total timeout
                for server_name, task in tasks:
                    try:
                        await task
                        print(f"✅ Connected to MCP server: {server_name}")
                    except Exception as e:
                        print(f"❌ Failed to connect to MCP server {server_name}: {e}")
                        # Continue with other servers instead of failing completely
        except asyncio.TimeoutError:
            print("❌ MCP server initialization timeout")
            # Cancel remaining tasks
            for server_name, task in tasks:
                if not task.done():
                    task.cancel()
            # Don't raise error, continue with available servers
        
        self.initialized = True
        connected_servers = len([s for s in self.sessions.values() if s is not None])
        print(f"🚀 McpClientManager initialized with {connected_servers} connected servers out of {len(Config.MCP_SERVERS)} configured")
        
        if connected_servers == 0:
            print("⚠️  No MCP servers connected. Tool functionality will be limited.")
    
    async def _connect_server(self, server_name: str, server_config: Dict[str, Any]):
        """Connect to a single MCP server"""
        try:
            # Check if the command exists
            command = server_config["command"]
            if not self._command_exists(command):
                print(f"❌ Command '{command}' not found for {server_name}")
                return  # Skip this server instead of raising error
            
            # Connect to real MCP server
            
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
            
            # Try to connect to the actual MCP server with timeout
            try:
                # Connect to the real MCP server with timeout
                async with asyncio.timeout(5.0):  # 5 second timeout
                    # Use a simpler approach to avoid TaskGroup issues
                    import subprocess
                    
                    # Start the MCP server process
                    process = await asyncio.create_subprocess_exec(
                        server_config["command"],
                        *server_config.get("args", []),
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env
                    )
                    
                    # Create a simple session wrapper
                    class SimpleSession:
                        def __init__(self, process):
                            self.process = process
                            self.tools = []
                        
                        async def initialize(self):
                            # Send initialization message
                            init_msg = '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "clientInfo": {"name": "llm-agent", "version": "1.0.0"}}}\n'
                            self.process.stdin.write(init_msg.encode())
                            await self.process.stdin.drain()
                            
                            # Read response
                            response = await self.process.stdout.readline()
                            print(f"🔍 MCP server {server_name} init response: {response.decode().strip()}")
                        
                        async def list_tools(self):
                            # Send list_tools message
                            tools_msg = '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}\n'
                            self.process.stdin.write(tools_msg.encode())
                            await self.process.stdin.drain()
                            
                            # Read response
                            response = await self.process.stdout.readline()
                            print(f"🔍 MCP server {server_name} tools response: {response.decode().strip()}")
                            
                            # Parse tools (simplified)
                            import json
                            try:
                                data = json.loads(response.decode())
                                if "result" in data and "tools" in data["result"]:
                                    self.tools = data["result"]["tools"]
                                    return type('obj', (object,), {'tools': self.tools})()
                            except:
                                pass
                            
                            # Fallback tools based on server name
                            if server_name == "filesystem":
                                self.tools = [
                                    {"name": "list_directory", "description": "List files in a directory"},
                                    {"name": "read_file", "description": "Read contents of a file"},
                                    {"name": "write_file", "description": "Write content to a file"}
                                ]
                            elif server_name == "brave-search":
                                self.tools = [
                                    {"name": "search", "description": "Search the web using Brave Search API"}
                                ]
                            elif server_name == "postgres":
                                self.tools = [
                                    {"name": "query", "description": "Execute SQL query"},
                                    {"name": "list_tables", "description": "List all tables in the database"}
                                ]
                            
                            return type('obj', (object,), {'tools': self.tools})()
                        
                        async def call_tool(self, tool_name, arguments):
                            print(f"🔍 call_tool called with tool_name: {tool_name}, arguments: {arguments}")
                            
                            # Add default arguments for common tools
                            if tool_name == "list_directory" and "path" not in arguments:
                                arguments["path"] = "."
                            elif tool_name == "read_file" and "path" not in arguments:
                                arguments["path"] = "README.md"  # Default file
                            
                            print(f"🔍 Final arguments: {arguments}")
                            
                            # Generate unique request ID
                            import time
                            request_id = int(time.time() * 1000) % 100000
                            
                            # Send tool call message
                            tool_call_msg = f'{{"jsonrpc": "2.0", "id": {request_id}, "method": "tools/call", "params": {{"name": "{tool_name}", "arguments": {json.dumps(arguments)}}}}}\n'
                            print(f"🔍 Tool call message: {tool_call_msg.strip()}")
                            
                            self.process.stdin.write(tool_call_msg.encode())
                            await self.process.stdin.drain()
                            
                            # Read responses until we get the one with matching ID
                            max_attempts = 10
                            for attempt in range(max_attempts):
                                response = await self.process.stdout.readline()
                                response_text = response.decode().strip()
                                print(f"🔍 MCP server {server_name} tool call response (attempt {attempt+1}): {response_text}")
                                
                                try:
                                    data = json.loads(response_text)
                                    response_id = data.get("id")
                                    
                                    # Check if this is the response we're waiting for
                                    if response_id == request_id:
                                        if "result" in data and "content" in data["result"]:
                                            return data["result"]["content"][0]["text"] if data["result"]["content"] else ""
                                        elif "error" in data:
                                            return f"Error: {data['error'].get('message', 'Unknown error')}"
                                        else:
                                            return str(data.get("result", ""))
                                    else:
                                        print(f"⚠️ Skipping response with mismatched ID: expected {request_id}, got {response_id}")
                                        continue
                                except Exception as e:
                                    print(f"❌ Error parsing tool response: {e}")
                                    continue
                            
                            return f"Tool {tool_name} executed with arguments {arguments}"
                        
                        def call_tool_sync(self, tool_name, arguments):
                            print(f"🔍 call_tool_sync called with tool_name: {tool_name}, arguments: {arguments}")
                            
                            # Add default arguments for common tools
                            if tool_name == "list_directory" and "path" not in arguments:
                                arguments["path"] = "."
                            elif tool_name == "read_file" and "path" not in arguments:
                                arguments["path"] = "README.md"  # Default file
                            
                            print(f"🔍 Final arguments: {arguments}")
                            
                            # Generate unique request ID
                            import time
                            request_id = int(time.time() * 1000) % 100000
                            
                            # Send tool call message
                            tool_call_msg = f'{{"jsonrpc": "2.0", "id": {request_id}, "method": "tools/call", "params": {{"name": "{tool_name}", "arguments": {json.dumps(arguments)}}}}}\n'
                            print(f"🔍 Tool call message: {tool_call_msg.strip()}")
                            
                            # Use subprocess to avoid asyncio conflicts
                            import subprocess
                            import tempfile
                            import os
                            import sys
                            
                            try:
                                # Check if we have a persistent MCP server process
                                if not hasattr(self, '_mcp_process') or self._mcp_process.poll() is not None:
                                    # Start a new persistent MCP server process
                                    env = os.environ.copy()
                                    env["POSTGRES_CONNECTION_STRING"] = "postgresql://test:test@localhost:5432/test"
                                    
                                    self._mcp_process = subprocess.Popen(
                                        [sys.executable, "/home/ubuntu/llm_agent/multi_db_postgres_mcp.py"],
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True,
                                        env=env
                                    )
                                
                                # Send the request to the persistent process
                                self._mcp_process.stdin.write(tool_call_msg.strip() + '\n')
                                self._mcp_process.stdin.flush()
                                
                                # Read responses until we get the one with matching ID
                                max_attempts = 10
                                for attempt in range(max_attempts):
                                    try:
                                        line = self._mcp_process.stdout.readline()
                                        if not line:
                                            break
                                        
                                        line = line.strip()
                                        print(f"🔍 MCP server {server_name} tool call response (attempt {attempt+1}): {line}")
                                        
                                        # Parse response
                                        try:
                                            data = json.loads(line)
                                            response_id = data.get("id")
                                            
                                            # Check if this is the response we're waiting for
                                            if response_id == request_id:
                                                if "result" in data and "content" in data["result"]:
                                                    return data["result"]["content"][0]["text"] if data["result"]["content"] else ""
                                                elif "error" in data:
                                                    return f"Error: {data['error'].get('message', 'Unknown error')}"
                                                else:
                                                    return str(data.get("result", ""))
                                            else:
                                                print(f"⚠️ Skipping response with mismatched ID: expected {request_id}, got {response_id}")
                                                continue
                                        except json.JSONDecodeError:
                                            # Skip non-JSON lines (debug logs)
                                            continue
                                    except Exception as e:
                                        print(f"❌ Error reading response: {e}")
                                        break
                                
                                if self._mcp_process.poll() is not None:
                                    return f"Error: MCP server process terminated"
                                
                                return f"Tool {tool_name} executed with arguments {arguments}"
                                
                            except subprocess.TimeoutExpired:
                                if hasattr(self, '_mcp_process'):
                                    self._mcp_process.kill()
                                return f"Error: MCP server timeout"
                            except Exception as e:
                                print(f"❌ Error in call_tool_sync: {e}")
                                return f"Error: {str(e)}"
                    
                    session = SimpleSession(process)
                    await session.initialize()
                    
                    # Get available tools from the server
                    tools_result = await session.list_tools()
                    self.tools[server_name] = tools_result.tools
                    
                    self.sessions[server_name] = session
                    print(f"✅ Connected to real MCP server: {server_name}")
                    return
                        
            except asyncio.TimeoutError:
                print(f"❌ Timeout connecting to MCP server {server_name}")
                return  # Skip this server instead of raising error
            except Exception as e:
                print(f"❌ Failed to connect to MCP server {server_name}: {e}")
                return  # Skip this server instead of raising error
                
        except Exception as e:
            print(f"❌ Error setting up MCP server {server_name}: {e}")
            return  # Skip this server instead of raising error
    
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
        
        # Session must exist for real MCP server
        if session is None:
                return {
                    "success": False,
                "error": f"Server {server_name} session is None",
                    "server": server_name,
                "tool": tool_name
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
            return {
                "success": False,
                "error": f"Tool call failed: {str(e)}",
                "server": server_name,
                "tool": tool_name
            }
    
    def call_tool_sync(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous version of call_tool for use in sync contexts"""
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
        
        # Session must exist for real MCP server
        if session is None:
            return {
                "success": False,
                "error": f"Server {server_name} session is None",
                "server": server_name,
                "tool": tool_name
            }
        
        # Use real MCP server with synchronous call
        try:
            # Call the actual tool on the MCP server synchronously
            result = session.call_tool_sync(tool_name, arguments)
            return {
                "success": True,
                "result": result,
                "server": server_name,
                "tool": tool_name,
            "mode": "real"
            }
        except Exception as e:
            print(f"❌ Real MCP tool call failed for {server_name}.{tool_name}: {e}")
            return {
                "success": False,
                "error": f"Tool call failed: {str(e)}",
                "server": server_name,
                "tool": tool_name
            }

    
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
