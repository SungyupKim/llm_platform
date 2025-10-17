#!/usr/bin/env python3
"""
Calculator MCP Server
Provides basic arithmetic operations: add, multiply, divide
"""

import asyncio
import json
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_request(request: dict) -> dict:
    """Handle MCP requests"""
    try:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        logger.info(f"🔍 handle_request received: method={method}, params={params}, id={request_id}")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "calculator-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "add",
                            "description": "Add two numbers together",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "a": {
                                        "type": "number",
                                        "description": "First number to add"
                                    },
                                    "b": {
                                        "type": "number",
                                        "description": "Second number to add"
                                    }
                                },
                                "required": ["a", "b"]
                            }
                        },
                        {
                            "name": "multiply",
                            "description": "Multiply two numbers together",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "a": {
                                        "type": "number",
                                        "description": "First number to multiply"
                                    },
                                    "b": {
                                        "type": "number",
                                        "description": "Second number to multiply"
                                    }
                                },
                                "required": ["a", "b"]
                            }
                        },
                        {
                            "name": "divide",
                            "description": "Divide first number by second number",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "a": {
                                        "type": "number",
                                        "description": "Dividend (number to be divided)"
                                    },
                                    "b": {
                                        "type": "number",
                                        "description": "Divisor (number to divide by)"
                                    }
                                },
                                "required": ["a", "b"]
                            }
                        }
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            logger.info(f"🔍 tools/call received: tool_name={tool_name}, arguments={arguments}")
            
            if tool_name == "add":
                result = await add(arguments.get("a", 0), arguments.get("b", 0))
            elif tool_name == "multiply":
                result = await multiply(arguments.get("a", 0), arguments.get("b", 0))
            elif tool_name == "divide":
                result = await divide(arguments.get("a", 0), arguments.get("b", 0))
            else:
                result = f"Unknown tool: {tool_name}"
            
            logger.info(f"🔍 tools/call result: {result}")
            
            # Return result in correct format
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    except Exception as e:
        logger.error(f"❌ Error in handle_request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

async def add(a: float, b: float) -> str:
    """Add two numbers"""
    try:
        result = a + b
        return f"{a} + {b} = {result}"
    except Exception as e:
        return f"Error adding {a} and {b}: {str(e)}"

async def multiply(a: float, b: float) -> str:
    """Multiply two numbers"""
    try:
        result = a * b
        return f"{a} × {b} = {result}"
    except Exception as e:
        return f"Error multiplying {a} and {b}: {str(e)}"

async def divide(a: float, b: float) -> str:
    """Divide first number by second number"""
    try:
        if b == 0:
            return f"Error: Cannot divide {a} by zero"
        result = a / b
        return f"{a} ÷ {b} = {result}"
    except Exception as e:
        return f"Error dividing {a} by {b}: {str(e)}"

async def main():
    """Main function to run the MCP server"""
    logger.info("🚀 Starting Calculator MCP Server")
    
    # Read from stdin and write to stdout
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            
            request = json.loads(line.strip())
            response = await handle_request(request)
            print(json.dumps(response))
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    logger.info("🚀 Calculator MCP Server starting...")
    asyncio.run(main())
