#!/usr/bin/env python3
"""
FastMCP RAG Server - FastMCP를 사용한 RAG MCP 서버
"""

from fastmcp import FastMCP
import base64
import os
from rag_system import RAGSystem

# FastMCP 서버 생성
mcp = FastMCP("RAG Server")

# RAG 시스템 초기화
rag_system = RAGSystem()

@mcp.tool()
def rag_upload_pdf(pdf_data: str, filename: str, metadata: dict = None) -> str:
    """Upload and process a PDF file"""
    try:
        if not pdf_data or not filename:
            return "❌ PDF 데이터와 파일명이 필요합니다."
        
        # Base64 디코딩
        pdf_bytes = base64.b64decode(pdf_data)
        
        # PDF 처리
        result = rag_system.process_pdf_bytes(pdf_bytes, filename, metadata)
        
        if result["success"]:
            return f"✅ PDF '{filename}' 업로드 및 처리 완료!\n" \
                   f"- 생성된 청크: {result['chunks_created']}개\n" \
                   f"- 총 청크: {result['total_chunks']}개\n" \
                   f"- 텍스트 길이: {result['text_length']}자"
        else:
            return f"❌ PDF 처리 실패: {result['error']}"
    
    except Exception as e:
        return f"❌ PDF 업로드 오류: {str(e)}"

@mcp.tool()
def rag_search(query: str, n_results: int = 5) -> str:
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
        return f"❌ 검색 오류: {str(e)}"

@mcp.tool()
def rag_chat(question: str, n_results: int = 3) -> str:
    """Ask questions about uploaded documents"""
    try:
        if not question.strip():
            return "❌ 질문이 비어있습니다."
        
        result = rag_system.rag_chat(question, n_results)
        
        if result.get('error'):
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
        return f"❌ 채팅 오류: {str(e)}"

@mcp.tool()
def rag_get_info() -> str:
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
        return f"❌ 정보 조회 오류: {str(e)}"

if __name__ == "__main__":
    # SSE 모드로 실행
    mcp.run(transport="sse", port=8010, host="0.0.0.0")
