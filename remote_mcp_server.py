#!/usr/bin/env python3
"""
Remote MCP Server - HTTP API wrapper for MCP servers
MCP 서버를 HTTP API로 래핑하여 원격 호출 가능하게 만드는 서버
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Remote MCP Server", description="HTTP API wrapper for MCP servers")

class MCPRequest(BaseModel):
    server_name: str
    tool_name: str
    arguments: Dict[str, Any] = {}

class MCPResponse(BaseModel):
    success: bool
    result: Any = None
    error: str = None

class MCPClient:
    """MCP 클라이언트 - 원격 MCP 서버와 통신"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.server_scripts = {
            "postgres": self.base_dir / "multi_db_postgres_mcp.py",
            "mysql": self.base_dir / "multi_db_mysql_mcp.py", 
            "calculator": self.base_dir / "calculator_mcp.py",
            "rag": self.base_dir / "rag_mcp.py"
        }
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """MCP 서버의 도구 호출"""
        try:
            if server_name not in self.server_scripts:
                return {
                    "success": False,
                    "error": f"Unknown server: {server_name}"
                }
            
            script_path = self.server_scripts[server_name]
            
            # MCP 요청 메시지 생성
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # 환경 변수 설정
            env = os.environ.copy()
            if server_name == "postgres":
                env["POSTGRES_CONNECTION_STRING"] = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
            elif server_name == "mysql":
                env["MYSQL_CONNECTION_STRING"] = os.getenv("MYSQL_CONNECTION_STRING", "mysql://test:test@localhost:3306/test")
            elif server_name == "rag":
                env.update({
                    "AWS_REGION": os.getenv("AWS_REGION", "ap-northeast-2"),
                    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", ""),
                    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "")
                })
            
            # MCP 서버 프로세스 실행
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # 요청 전송
            request_json = json.dumps(request) + "\n"
            stdout, stderr = await process.communicate(input=request_json.encode())
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"Server error: {stderr.decode()}"
                }
            
            # 응답 파싱
            response_lines = stdout.decode().strip().split('\n')
            for line in response_lines:
                if line.strip():
                    try:
                        response = json.loads(line)
                        if "result" in response:
                            return {
                                "success": True,
                                "result": response["result"]
                            }
                        elif "error" in response:
                            return {
                                "success": False,
                                "error": response["error"]
                            }
                    except json.JSONDecodeError:
                        continue
            
            return {
                "success": False,
                "error": "Invalid response format"
            }
            
        except Exception as e:
            logger.error(f"Error calling MCP tool: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# MCP 클라이언트 인스턴스
mcp_client = MCPClient()

@app.get("/")
async def root():
    """서버 상태 확인"""
    return {
        "status": "running",
        "available_servers": list(mcp_client.server_scripts.keys()),
        "description": "Remote MCP Server - HTTP API wrapper for MCP servers"
    }

@app.get("/servers")
async def list_servers():
    """사용 가능한 MCP 서버 목록"""
    return {
        "servers": list(mcp_client.server_scripts.keys()),
        "descriptions": {
            "postgres": "PostgreSQL database operations",
            "mysql": "MySQL database operations", 
            "calculator": "Mathematical calculations",
            "rag": "RAG system for document processing"
        }
    }

@app.post("/call", response_model=MCPResponse)
async def call_mcp_tool(request: MCPRequest):
    """MCP 도구 호출"""
    try:
        result = await mcp_client.call_tool(
            request.server_name,
            request.tool_name, 
            request.arguments
        )
        
        if result["success"]:
            return MCPResponse(success=True, result=result["result"])
        else:
            return MCPResponse(success=False, error=result["error"])
            
    except Exception as e:
        logger.error(f"Error in call_mcp_tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
