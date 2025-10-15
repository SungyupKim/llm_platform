#!/usr/bin/env python3
"""
Test script for MCP server connections
"""

import asyncio
from mcp_client import mcp_client

async def test_mcp_connections():
    """Test MCP server connections"""
    print("🧪 Testing MCP Server Connections")
    print("=" * 50)
    
    try:
        # Initialize MCP client
        await mcp_client.initialize()
        
        # List available servers
        servers = await mcp_client.list_servers()
        print(f"📋 Available servers: {servers}")
        
        # Get available tools
        tools = await mcp_client.get_available_tools()
        print(f"\n🔧 Available tools:")
        for server_name, server_tools in tools.items():
            print(f"  {server_name}:")
            for tool in server_tools:
                print(f"    - {tool['name']}: {tool['description']}")
        
        # Test tool calls
        print(f"\n🧪 Testing tool calls:")
        
        # Test filesystem tools
        if "filesystem" in servers:
            print("\n📁 Testing filesystem tools:")
            
            # Test list directory
            result = await mcp_client.call_tool("filesystem", "list_directory", {"path": "."})
            print(f"  list_directory: {result}")
            
            # Test read file
            result = await mcp_client.call_tool("filesystem", "read_file", {"path": "config.py"})
            print(f"  read_file: {result}")
        
        # Test search tools
        if "brave-search" in servers:
            print("\n🔍 Testing search tools:")
            result = await mcp_client.call_tool("brave-search", "search", {"query": "Python programming"})
            print(f"  search: {result}")
        
        # Test database tools
        if "postgres" in servers:
            print("\n🗄️  Testing database tools:")
            result = await mcp_client.call_tool("postgres", "list_tables", {})
            print(f"  list_tables: {result}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        await mcp_client.close()
        print("\n🔌 MCP connections closed")

if __name__ == "__main__":
    asyncio.run(test_mcp_connections())

