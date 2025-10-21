#!/usr/bin/env python3
"""
MCP Server SSE Runner - MCP 서버를 SSE 모드로 실행
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path
import subprocess
from typing import Dict, Any
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP SSE Server", description="MCP servers with SSE support")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MCPServerManager:
    """MCP 서버 관리자 - SSE 모드로 실행"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.servers = {
            "postgres": {
                "script": self.base_dir / "multi_db_postgres_mcp.py",
                "env": {
                    "POSTGRES_CONNECTION_STRING": os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
                }
            },
            "mysql": {
                "script": self.base_dir / "multi_db_mysql_mcp.py",
                "env": {
                    "MYSQL_CONNECTION_STRING": os.getenv("MYSQL_CONNECTION_STRING", "mysql://test:test@localhost:3306/test")
                }
            },
            "calculator": {
                "script": self.base_dir / "calculator_mcp.py",
                "env": {}
            },
            "rag": {
                "script": self.base_dir / "rag_mcp.py",
                "env": {
                    "AWS_REGION": os.getenv("AWS_REGION", "ap-northeast-2"),
                    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", ""),
                    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "")
                }
            }
        }
    
    async def call_mcp_server_sse(self, server_name: str, tool_name: str, arguments: Dict[str, Any]):
        """MCP 서버를 SSE로 호출"""
        if server_name not in self.servers:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Unknown server: {server_name}'})}\n\n"
            return
        
        server_config = self.servers[server_name]
        script_path = server_config["script"]
        
        # MCP 요청 생성
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            # 환경 변수 설정
            env = os.environ.copy()
            env.update(server_config["env"])
            
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
                yield f"data: {json.dumps({'type': 'error', 'message': f'Server error: {stderr.decode()}'})}\n\n"
                return
            
            # 응답 처리
            response_lines = stdout.decode().strip().split('\n')
            for line in response_lines:
                if line.strip():
                    try:
                        response = json.loads(line)
                        if "result" in response:
                            yield f"data: {json.dumps({'type': 'result', 'data': response['result']})}\n\n"
                        elif "error" in response:
                            yield f"data: {json.dumps({'type': 'error', 'data': response['error']})}\n\n"
                    except json.JSONDecodeError:
                        # 로그 메시지
                        yield f"data: {json.dumps({'type': 'log', 'message': line})}\n\n"
            
        except Exception as e:
            logger.error(f"Error calling MCP server: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

# MCP 서버 관리자 인스턴스
mcp_manager = MCPServerManager()

@app.get("/")
async def root():
    """서버 정보"""
    return {
        "name": "MCP SSE Server",
        "version": "1.0.0",
        "available_servers": list(mcp_manager.servers.keys()),
        "description": "MCP servers with Server-Sent Events support"
    }

@app.get("/servers")
async def list_servers():
    """사용 가능한 MCP 서버 목록"""
    return {
        "servers": list(mcp_manager.servers.keys()),
        "descriptions": {
            "postgres": "PostgreSQL database operations",
            "mysql": "MySQL database operations",
            "calculator": "Mathematical calculations",
            "rag": "RAG system for document processing"
        }
    }

@app.get("/sse/{server_name}/{tool_name}")
async def call_mcp_sse(server_name: str, tool_name: str, request: Request):
    """SSE를 통한 MCP 서버 호출"""
    # 쿼리 파라미터를 arguments로 변환
    arguments = {}
    
    # request 객체에서 쿼리 파라미터 추출
    query_params = request.query_params
    for key, value in query_params.items():
        # 숫자로 변환 시도
        try:
            if '.' in value:
                arguments[key] = float(value)
            else:
                arguments[key] = int(value)
        except ValueError:
            arguments[key] = value
    
    async def event_generator():
        async for event in mcp_manager.call_mcp_server_sse(server_name, tool_name, arguments):
            yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "servers": list(mcp_manager.servers.keys())}

if __name__ == "__main__":
    print("🚀 Starting MCP SSE Server...")
    print("Available servers:", list(mcp_manager.servers.keys()))
    print("SSE endpoint: http://localhost:8004/sse/{server_name}/{tool_name}")
    
    uvicorn.run(app, host="0.0.0.0", port=8004)
