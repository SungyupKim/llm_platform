"""
Hybrid supervisor that tries LLM first, falls back to simple rules
"""

from typing import Dict, List, Any, TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from supervisor import SupervisorAgent
from simple_supervisor import SimpleSupervisorAgent

class SupervisorState(TypedDict):
    """State for the supervisor agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    current_task: str
    available_tools: Dict[str, List[Dict[str, Any]]]
    selected_worker: str
    worker_result: str
    iteration_count: int
    is_finished: bool

class HybridSupervisorAgent:
    """Hybrid supervisor that tries LLM first, falls back to simple rules"""
    
    def __init__(self):
        self.llm_supervisor = SupervisorAgent()
        self.simple_supervisor = SimpleSupervisorAgent()
        self.llm_available = True
    
    async def decide_worker(self, state: SupervisorState) -> SupervisorState:
        """Decide which worker should handle the current task"""
        
        if self.llm_available:
            try:
                print("🤖 Trying LLM supervisor...")
                result = await self.llm_supervisor.decide_worker(state)
                print("✅ LLM supervisor succeeded")
                return result
            except Exception as e:
                print(f"⚠️  LLM supervisor failed: {e}")
                print("🔄 Falling back to simple supervisor...")
                self.llm_available = False
        
        # Fallback to simple supervisor
        print("📋 Using simple rule-based supervisor")
        return await self.simple_supervisor.decide_worker(state)
    
    async def evaluate_result(self, state: SupervisorState) -> SupervisorState:
        """Evaluate the worker's result and decide next steps"""
        
        if self.llm_available:
            try:
                print("🤖 Trying LLM evaluation...")
                result = await self.llm_supervisor.evaluate_result(state)
                print("✅ LLM evaluation succeeded")
                return result
            except Exception as e:
                print(f"⚠️  LLM evaluation failed: {e}")
                print("🔄 Falling back to simple evaluation...")
                self.llm_available = False
        
        # Fallback to simple evaluation
        print("📋 Using simple rule-based evaluation")
        return await self.simple_supervisor.evaluate_result(state)
