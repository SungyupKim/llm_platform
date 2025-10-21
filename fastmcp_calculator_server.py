#!/usr/bin/env python3
"""
FastMCP Calculator Server - FastMCP를 사용한 계산기 MCP 서버
"""

from fastmcp import FastMCP
import asyncio

# FastMCP 서버 생성
mcp = FastMCP("Calculator Server")

@mcp.tool()
def add(a: float, b: float) -> str:
    """Add two numbers together"""
    result = a + b
    return f"{a} + {b} = {result}"

@mcp.tool()
def multiply(a: float, b: float) -> str:
    """Multiply two numbers together"""
    result = a * b
    return f"{a} × {b} = {result}"

@mcp.tool()
def divide(a: float, b: float) -> str:
    """Divide first number by second number"""
    if b == 0:
        return "Error: Division by zero"
    result = a / b
    return f"{a} ÷ {b} = {result}"

if __name__ == "__main__":
    # SSE 모드로 실행
    mcp.run(transport="sse", port=8009, host="0.0.0.0")
