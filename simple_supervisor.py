"""
Simple rule-based supervisor that doesn't require LLM access
"""

from typing import Dict, List, Any, TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class SupervisorState(TypedDict):
    """State for the supervisor agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    current_task: str
    available_tools: Dict[str, List[Dict[str, Any]]]
    selected_worker: str
    worker_result: str
    iteration_count: int
    is_finished: bool

class SimpleSupervisorAgent:
    """Simple rule-based supervisor agent that doesn't require LLM"""
    
    def __init__(self):
        pass
    
    async def decide_worker(self, state: SupervisorState) -> SupervisorState:
        """Decide which worker should handle the current task using simple rules"""
        
        # Get the latest user message
        user_message = state["messages"][-1].content if state["messages"] else ""
        user_message_lower = user_message.lower()
        
        print(f"🔍 Analyzing user request: {user_message}")
        
        # Simple keyword-based worker selection
        if any(keyword in user_message_lower for keyword in [
            "file", "read", "write", "directory", "folder", "create", "delete", "list", "ls"
        ]):
            selected_worker = "filesystem_worker"
            task_desc = "Perform file system operations"
            
        elif any(keyword in user_message_lower for keyword in [
            "search", "find", "web", "internet", "google", "look up", "information"
        ]):
            selected_worker = "search_worker"
            task_desc = "Perform web search operations"
            
        elif any(keyword in user_message_lower for keyword in [
            "database", "db", "sql", "query", "table", "insert", "update", "select"
        ]):
            selected_worker = "database_worker"
            task_desc = "Perform database operations"
            
        elif any(keyword in user_message_lower for keyword in [
            "aws", "s3", "ec2", "lambda", "cloud", "upload", "bucket"
        ]):
            selected_worker = "aws_worker"
            task_desc = "Perform AWS operations"
            
        else:
            # Default to filesystem for general tasks
            selected_worker = "filesystem_worker"
            task_desc = "Handle the user request"
        
        # Update state
        state["selected_worker"] = selected_worker
        state["current_task"] = task_desc
        state["is_finished"] = False
        
        # Add decision message
        decision_msg = AIMessage(content=f"Simple supervisor selected: {selected_worker} for task: {task_desc}")
        state["messages"].append(decision_msg)
        
        print(f"✅ Selected worker: {selected_worker}")
        
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
