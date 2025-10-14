from typing import Dict, List, Any, TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from config import Config
from bedrock_client import bedrock_client
import json

class SupervisorState(TypedDict):
    """State for the supervisor agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    current_task: str
    available_tools: Dict[str, List[Dict[str, Any]]]
    selected_worker: str
    worker_result: str
    iteration_count: int
    is_finished: bool

class SupervisorAgent:
    """Supervisor agent that decides which worker to use for each task"""
    
    def __init__(self):
        # Use the fallback Bedrock client
        self.llm = bedrock_client.get_llm()
        
        self.system_prompt = """You are a supervisor agent that selects the best worker for each task.

Available workers:
- filesystem_worker: For file operations (read, write, list, create directories)
- search_worker: For web search and information retrieval  
- database_worker: For database operations (query, insert, update, delete)
- aws_worker: For AWS services (S3, EC2, Lambda, etc.)

IMPORTANT: Respond with ONLY the worker name. No other text, no explanations, no formatting.

Examples:
- User asks to "list files" → respond: filesystem_worker
- User asks to "search for Python" → respond: search_worker
- User asks to "query database" → respond: database_worker
- User asks to "upload to S3" → respond: aws_worker

Just respond with the worker name."""

    async def decide_worker(self, state: SupervisorState) -> SupervisorState:
        """Decide which worker should handle the current task"""
        
        # Get the latest user message
        user_message = state["messages"][-1].content if state["messages"] else ""
        
        # Create simple prompt for worker selection
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", f"User request: {user_message}")
        ])
        
        # Get LLM response
        response = await self.llm.ainvoke(prompt.format_messages())
        
        # Debug: Print the raw response
        print(f"🔍 Raw supervisor response: {response.content}")
        
        # Extract worker name from response
        response_text = response.content.strip().lower()
        
        # Simple worker selection based on response
        if "filesystem_worker" in response_text:
            selected_worker = "filesystem_worker"
        elif "search_worker" in response_text:
            selected_worker = "search_worker"
        elif "database_worker" in response_text:
            selected_worker = "database_worker"
        elif "aws_worker" in response_text:
            selected_worker = "aws_worker"
        else:
            # Fallback: analyze user message for keywords
            user_message_lower = user_message.lower()
            if any(keyword in user_message_lower for keyword in ["file", "read", "write", "directory", "folder", "create", "delete", "list"]):
                selected_worker = "filesystem_worker"
            elif any(keyword in user_message_lower for keyword in ["search", "find", "web", "internet", "google", "look up"]):
                selected_worker = "search_worker"
            elif any(keyword in user_message_lower for keyword in ["database", "db", "sql", "query", "table", "insert", "update"]):
                selected_worker = "database_worker"
            elif any(keyword in user_message_lower for keyword in ["aws", "s3", "ec2", "lambda", "cloud"]):
                selected_worker = "aws_worker"
            else:
                selected_worker = "filesystem_worker"  # Default
        
        # Update state
        state["selected_worker"] = selected_worker
        state["current_task"] = user_message
        state["is_finished"] = False
        
        # Add decision message
        decision_msg = AIMessage(content=f"Supervisor selected: {selected_worker}")
        state["messages"].append(decision_msg)
        
        return state
    
    async def evaluate_result(self, state: SupervisorState) -> SupervisorState:
        """Evaluate the worker's result and decide next steps"""
        
        if state["is_finished"]:
            return state
        
        # Simple evaluation - just check if we have a result
        if state["worker_result"] and len(state["worker_result"].strip()) > 0:
            # Task is complete if we have a result
            state["is_finished"] = True
            print("✅ Task completed - worker provided result")
        else:
            # Task is not complete if no result
            state["is_finished"] = False
            print("⏳ Task not complete - no result from worker")
        
        return state
