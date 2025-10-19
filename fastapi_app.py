from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any, AsyncGenerator
import asyncio
import json
import uvicorn
import os
import logging
from streaming_agent import StreamingAgent
from config import Config
from rag_system import RAGSystem

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG to see more details
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('app.log')  # File output
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Agent API", description="Streaming LLM Agent with Tool Support and RAG")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Global instances
agent = None
rag_system = None

class ChatRequest(BaseModel):
    message: str
    conversation_history: List[Dict[str, str]] = []

class ChatResponse(BaseModel):
    message: str
    used_tools: bool = False

@app.on_event("startup")
async def startup_event():
    """Initialize the agent and RAG system on startup"""
    global agent, rag_system
    try:
        logger.info("✅ Initializing ChatBedrock...")
        logger.info("✅ AWS credentials verified")
        agent = StreamingAgent()
        logger.info("🚀 Agent initialized successfully")
        
        logger.info("✅ Initializing RAG System...")
        rag_system = RAGSystem()
        logger.info("🚀 RAG System initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize systems: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    global agent
    if agent:
        await agent.close()

async def stream_agent_response(message: str, conversation_history: List[Dict[str, str]] = None) -> AsyncGenerator[str, None]:
    """Stream agent response as Server-Sent Events"""
    logger.info(f"📨 Received message: {message[:100]}...")
    
    if not agent:
        logger.error("❌ Agent not initialized")
        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent not initialized'})}\n\n"
        return
    
    try:
        # Convert conversation history to proper format
        from langchain_core.messages import HumanMessage, AIMessage
        history = []
        if conversation_history:
            logger.info(f"📚 Processing {len(conversation_history)} conversation history items")
            for msg in conversation_history:
                if msg.get("role") == "user":
                    history.append(HumanMessage(content=msg["content"]))
                elif msg.get("role") == "assistant":
                    history.append(AIMessage(content=msg["content"]))
        
        # Stream the agent response
        logger.info("🚀 Starting agent streaming...")
        async for update in agent.run_streaming(message, history):
            logger.debug(f"📤 Streaming update: {update['type']}")
            
            if update["type"] == "step":
                yield f"data: {json.dumps({'type': 'step', 'message': update['message'], 'details': update.get('details', '')})}\n\n"
            elif update["type"] == "stream":
                yield f"data: {json.dumps({'type': 'stream', 'chunk': update['chunk']})}\n\n"
            elif update["type"] == "tool_result":
                logger.info(f"🔧 Tool result: {update.get('tool_name', 'Unknown')}")
                yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': update.get('tool_name', 'Unknown'), 'result': update.get('result', '')})}\n\n"
            elif update["type"] == "response" or update["type"] == "response_complete":
                logger.info(f"✅ Response complete, used_tools: {update.get('used_tools', False)}")
                # Don't send the full message again, just the completion signal
                yield f"data: {json.dumps({'type': 'response_complete', 'used_tools': update.get('used_tools', False)})}\n\n"
            elif update["type"] == "error":
                logger.error(f"❌ Agent error: {update['message']}")
                yield f"data: {json.dumps({'type': 'error', 'message': update['message']})}\n\n"
            
            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.01)
        
        logger.info("🏁 Agent streaming completed")
    
    except Exception as e:
        logger.error(f"❌ Streaming error: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': f'Error: {str(e)}'})}\n\n"

@app.get("/")
async def root():
    """Serve the main interface with navigation"""
    return templates.TemplateResponse("main.html", {"request": {}})

@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "message": "LLM Agent API",
        "version": "1.0.0",
        "endpoints": {
            "POST /chat": "Streaming chat endpoint",
            "POST /chat/simple": "Simple non-streaming chat endpoint",
            "GET /health": "Health check",
            "GET /docs": "API documentation"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
        "timestamp": asyncio.get_event_loop().time()
    }

@app.post("/chat")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events"""
    return StreamingResponse(
        stream_agent_response(request.message, request.conversation_history),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "*"
        }
    )

@app.post("/chat/simple")
async def chat_simple(request: ChatRequest):
    """Simple non-streaming chat endpoint"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    try:
        # Convert conversation history
        from langchain_core.messages import HumanMessage, AIMessage
        history = []
        if request.conversation_history:
            for msg in request.conversation_history:
                if msg.get("role") == "user":
                    history.append(HumanMessage(content=msg["content"]))
                elif msg.get("role") == "assistant":
                    history.append(AIMessage(content=msg["content"]))
        
        # Collect all updates
        final_response = ""
        used_tools = False
        
        async for update in agent.run_streaming(request.message, history):
            if update["type"] == "response" or update["type"] == "response_complete":
                final_response = update["message"]
                used_tools = update.get("used_tools", False)
            elif update["type"] == "error":
                raise HTTPException(status_code=500, detail=update["message"])
        
        return ChatResponse(message=final_response, used_tools=used_tools)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# RAG System Routes
@app.get("/rag")
async def rag_interface():
    """Serve the RAG interface"""
    return templates.TemplateResponse("rag.html", {"request": {}})

@app.post("/rag/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and process PDF file"""
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        # Read file content
        content = await file.read()
        
        # Process PDF using bytes method
        result = rag_system.process_pdf_bytes(content, file.filename)
        
        if result.get("success", False):
            return {
                "message": result.get("message", f"PDF '{file.filename}' processed successfully"),
                "chunks_created": result.get("chunks_created", 0),
                "total_chunks": result.get("total_chunks", 0)
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "PDF processing failed"))
            
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.post("/rag/search")
async def search_documents(query: str = Form(...), k: int = Form(5)):
    """Search documents using RAG"""
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    try:
        results = await rag_system.search(query, n_results=k)
        return {
            "query": query,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching documents: {str(e)}")

@app.get("/rag/collection-info")
async def get_collection_info():
    """Get collection information"""
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    try:
        info = rag_system.get_collection_info()
        return info
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting collection info: {str(e)}")

@app.post("/rag/reset")
async def reset_collection():
    """Reset the collection"""
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    try:
        await rag_system.reset_collection()
        return {"message": "Collection reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting collection: {e}")
        raise HTTPException(status_code=500, detail=f"Error resetting collection: {str(e)}")

@app.post("/rag/chat")
async def rag_chat(query: str = Form(...), n_results: int = Form(3)):
    """RAG 기반 채팅 - 검색된 문서를 참조하여 LLM이 답변 생성"""
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    try:
        result = await rag_system.rag_chat(query, n_results=n_results)
        return result
    except Exception as e:
        logger.error(f"Error in RAG chat: {e}")
        raise HTTPException(status_code=500, detail=f"Error in RAG chat: {str(e)}")

async def stream_rag_response(query: str, n_results: int = 3) -> AsyncGenerator[str, None]:
    """Stream RAG response as Server-Sent Events"""
    logger.info(f"📨 RAG streaming request: {query[:100]}...")
    
    if not rag_system:
        logger.error("❌ RAG system not initialized")
        yield f"data: {json.dumps({'type': 'error', 'message': 'RAG system not initialized'})}\n\n"
        return
    
    try:
        # Stream the RAG response
        logger.info("🚀 Starting RAG streaming...")
        async for update in rag_system.rag_chat_stream(query, n_results=n_results):
            logger.debug(f"📤 RAG streaming update: {update['type']}")
            
            if update["type"] == "search_start":
                yield f"data: {json.dumps({'type': 'search_start', 'message': update['message']})}\n\n"
            elif update["type"] == "search_complete":
                yield f"data: {json.dumps({'type': 'search_complete', 'message': update['message'], 'sources': update.get('sources', [])})}\n\n"
            elif update["type"] == "generation_start":
                yield f"data: {json.dumps({'type': 'generation_start', 'message': update['message']})}\n\n"
            elif update["type"] == "stream":
                yield f"data: {json.dumps({'type': 'stream', 'chunk': update['chunk']})}\n\n"
            elif update["type"] == "response_complete":
                logger.info("✅ RAG response complete")
                yield f"data: {json.dumps({'type': 'response_complete', 'message': update['message'], 'sources': update.get('sources', []), 'query': update.get('query', ''), 'total_sources': update.get('total_sources', 0)})}\n\n"
            elif update["type"] == "error":
                logger.error(f"❌ RAG error: {update['message']}")
                yield f"data: {json.dumps({'type': 'error', 'message': update['message']})}\n\n"
            
            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.01)
        
        logger.info("🏁 RAG streaming completed")
    
    except Exception as e:
        logger.error(f"❌ RAG streaming error: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': f'Error: {str(e)}'})}\n\n"

@app.post("/rag/chat/stream")
async def rag_chat_stream(query: str = Form(...), n_results: int = Form(3)):
    """RAG 기반 스트리밍 채팅 - 검색된 문서를 참조하여 LLM이 스트리밍으로 답변 생성"""
    return StreamingResponse(
        stream_rag_response(query, n_results),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "*"
        }
    )

# Agent Chat with File Upload
@app.post("/chat/upload")
async def chat_upload_file(file: UploadFile = File(...)):
    """Upload PDF file for Agent chat - integrates with RAG MCP"""
    if not file.filename.endswith('.pdf'):
        return {
            "success": False,
            "error": "Only PDF files are allowed"
        }
    
    try:
        # Read file content
        content = await file.read()
        
        # Process PDF using RAG system
        if rag_system:
            result = rag_system.process_pdf_bytes(content, file.filename)
            
            if result.get("success", False):
                return {
                    "success": True,
                    "message": f"PDF '{file.filename}' uploaded and processed successfully",
                    "chunks_created": result.get("chunks_created", 0),
                    "total_chunks": result.get("total_chunks", 0),
                    "filename": file.filename
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "PDF processing failed")
                }
        else:
            return {
                "success": False,
                "error": "RAG system not initialized"
            }
            
    except Exception as e:
        logger.error(f"Error processing PDF in chat upload: {e}")
        return {
            "success": False,
            "error": f"Error processing PDF: {str(e)}"
        }

if __name__ == "__main__":
    # Configure uvicorn logging
    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
        access_log=True,
        use_colors=True
    )
