from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, AsyncGenerator
import asyncio
import json
import uvicorn
import os
import logging
from streaming_agent import StreamingAgent
from bedrock_client import bedrock_client
from config import Config

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

app = FastAPI(title="LLM Agent API", description="Streaming LLM Agent with Tool Support")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global agent instance
agent = None

class ChatRequest(BaseModel):
    message: str
    conversation_history: List[Dict[str, str]] = []

class ChatResponse(BaseModel):
    message: str
    used_tools: bool = False

@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup"""
    global agent
    try:
        logger.info("✅ Initializing ChatBedrock...")
        logger.info("✅ AWS credentials verified")
        agent = StreamingAgent()
        logger.info("🚀 Agent initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize agent: {e}")
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
    """Serve the chat interface"""
    return FileResponse("static/index.html")

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

if __name__ == "__main__":
    # Configure uvicorn logging
    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
        use_colors=True
    )
