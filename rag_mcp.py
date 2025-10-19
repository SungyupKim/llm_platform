#!/usr/bin/env python3
"""
RAG (Retrieval-Augmented Generation) MCP Server
PDF 파싱, 청킹, 임베딩, 벡터 검색을 통한 RAG 시스템을 MCP로 제공
"""

import asyncio
import json
import sys
import logging
import base64
from typing import List, Dict, Any, Optional

# Import RAGSystem from rag_system.py
from rag_system import RAGSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 RAG 시스템 인스턴스
rag_system = RAGSystem()

async def handle_request(request: dict) -> dict:
    """Handle MCP requests"""
    try:
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "rag-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "rag_upload_pdf",
                            "description": "Upload and process a PDF file for RAG system",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "pdf_data": {
                                        "type": "string",
                                        "description": "Base64 encoded PDF file data"
                                    },
                                    "filename": {
                                        "type": "string",
                                        "description": "Name of the PDF file"
                                    },
                                    "metadata": {
                                        "type": "object",
                                        "description": "Optional metadata for the document",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "author": {"type": "string"},
                                            "category": {"type": "string"},
                                            "tags": {"type": "array", "items": {"type": "string"}}
                                        }
                                    }
                                },
                                "required": ["pdf_data", "filename"]
                            }
                        },
                        {
                            "name": "rag_search",
                            "description": "Search for relevant documents in the RAG system",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Search query"
                                    },
                                    "n_results": {
                                        "type": "integer",
                                        "description": "Number of results to return (default: 5)",
                                        "default": 5
                                    }
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "rag_chat",
                            "description": "Ask questions and get AI-powered answers based on uploaded documents",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "question": {
                                        "type": "string",
                                        "description": "Question to ask about the documents"
                                    },
                                    "n_results": {
                                        "type": "integer",
                                        "description": "Number of documents to retrieve for context (default: 3)",
                                        "default": 3
                                    }
                                },
                                "required": ["question"]
                            }
                        },
                        {
                            "name": "rag_get_info",
                            "description": "Get information about the RAG system and collection",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "rag_upload_pdf":
                result = await upload_pdf(
                    arguments.get("pdf_data"),
                    arguments.get("filename"),
                    arguments.get("metadata")
                )
            elif tool_name == "rag_search":
                result = await search_documents(
                    arguments.get("query"),
                    arguments.get("n_results", 5)
                )
            elif tool_name == "rag_chat":
                result = await chat_with_documents(
                    arguments.get("question"),
                    arguments.get("n_results", 3)
                )
            elif tool_name == "rag_get_info":
                result = await get_rag_info()
            else:
                result = f"Unknown tool: {tool_name}"
            
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    except Exception as e:
        logger.error(f"Request handling error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

async def upload_pdf(pdf_data: str, filename: str, metadata: dict = None) -> str:
    """Upload and process a PDF file"""
    try:
        if not pdf_data or not filename:
            return "❌ PDF 데이터와 파일명이 필요합니다."
        
        # Decode base64 PDF data
        pdf_bytes = base64.b64decode(pdf_data)
        
        # Process PDF
        result = rag_system.process_pdf_bytes(pdf_bytes, filename, metadata)
        
        if result["success"]:
            return f"✅ PDF '{filename}' 업로드 및 처리 완료!\n" \
                   f"- 생성된 청크: {result['chunks_created']}개\n" \
                   f"- 총 청크: {result['total_chunks']}개\n" \
                   f"- 텍스트 길이: {result['text_length']}자"
        else:
            return f"❌ PDF 처리 실패: {result['error']}"
    
    except Exception as e:
        logger.error(f"PDF 업로드 오류: {e}")
        return f"❌ PDF 업로드 오류: {str(e)}"

async def search_documents(query: str, n_results: int = 5) -> str:
    """Search for relevant documents"""
    try:
        if not query.strip():
            return "❌ 검색 쿼리가 비어있습니다."
        
        results = rag_system.search(query, n_results)
        
        if not results:
            return f"🔍 '{query}'에 대한 검색 결과가 없습니다."
        
        response = f"🔍 '{query}' 검색 결과 ({len(results)}개):\n\n"
        
        for i, result in enumerate(results, 1):
            response += f"**결과 {i}:**\n"
            metadata = result.get('metadata', {})
            response += f"문서: {metadata.get('filename', 'Unknown')}\n"
            response += f"내용: {result['text'][:200]}...\n"
            response += f"유사도: {1 - result['distance']:.3f}\n\n"
        
        return response
    
    except Exception as e:
        logger.error(f"검색 오류: {e}")
        return f"❌ 검색 오류: {str(e)}"

async def chat_with_documents(question: str, n_results: int = 3) -> str:
    """Ask questions and get AI-powered answers"""
    try:
        if not question.strip():
            return "❌ 질문이 비어있습니다."
        
        result = rag_system.rag_chat(question, n_results)
        
        if "error" in result:
            return f"❌ 채팅 오류: {result['error']}"
        
        response = f"🤖 질문: {result['query']}\n\n"
        response += f"답변: {result['answer']}\n\n"
        
        if result['sources']:
            response += "📚 참조 문서:\n"
            for i, source in enumerate(result['sources'], 1):
                metadata = source.get('metadata', {})
                filename = metadata.get('filename', 'Unknown')
                response += f"{i}. {filename}\n"
        
        return response
    
    except Exception as e:
        logger.error(f"채팅 오류: {e}")
        return f"❌ 채팅 오류: {str(e)}"

async def get_rag_info() -> str:
    """Get RAG system information"""
    try:
        info = rag_system.get_collection_info()
        
        response = "📊 RAG 시스템 정보:\n\n"
        response += f"📁 컬렉션명: {info.get('collection_name', 'Unknown')}\n"
        response += f"📄 총 문서 수: {info.get('total_documents', 0)}개\n"
        response += f"📏 청크 크기: {info.get('chunk_size', 0)}자\n"
        response += f"🔄 청크 겹침: {info.get('chunk_overlap', 0)}자\n"
        
        return response
    
    except Exception as e:
        logger.error(f"정보 조회 오류: {e}")
        return f"❌ 정보 조회 오류: {str(e)}"

async def main():
    """Main MCP server loop"""
    logger.info("RAG MCP Server starting...")
    
    try:
        while True:
            # Read request from stdin
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            
            try:
                request = json.loads(line.strip())
                response = await handle_request(request)
                print(json.dumps(response, ensure_ascii=False))
                sys.stdout.flush()
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                logger.error(f"Request processing error: {e}")
    
    except KeyboardInterrupt:
        logger.info("RAG MCP Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
