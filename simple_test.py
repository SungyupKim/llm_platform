#!/usr/bin/env python3
"""
Simple test for MCP client
"""

import asyncio
from mcp_client import mcp_client

async def simple_test():
    """Simple test of MCP client"""
    print("🧪 Simple MCP Test")
    print("=" * 30)
    
    try:
        # Initialize MCP client
        await mcp_client.initialize()
        
        # Test simple tool call
        result = await mcp_client.call_tool("filesystem", "list_directory", {"path": "."})
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(simple_test())
