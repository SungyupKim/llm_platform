from typing import Dict, List, Any, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from supervisor import SupervisorAgent, SupervisorState
from workers import execute_worker_task, WORKERS
from mcp_client import mcp_client
from config import Config
import asyncio

class AgentState(TypedDict):
    """Main state for the LangGraph agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    current_task: str
    available_tools: Dict[str, List[Dict[str, Any]]]
    selected_worker: str
    worker_result: str
    iteration_count: int
    is_finished: bool
    error_message: str

class LangGraphAgent:
    """LangGraph-based agent with supervisor pattern"""
    
    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create the state graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("initialize", self._initialize_node)
        workflow.add_node("supervisor_decision", self._supervisor_decision_node)
        workflow.add_node("execute_worker", self._execute_worker_node)
        workflow.add_node("evaluate_result", self._evaluate_result_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Add edges
        workflow.set_entry_point("initialize")
        
        workflow.add_edge("initialize", "supervisor_decision")
        
        workflow.add_conditional_edges(
            "supervisor_decision",
            self._should_continue,
            {
                "continue": "execute_worker",
                "finished": END,
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("execute_worker", "evaluate_result")
        
        workflow.add_conditional_edges(
            "evaluate_result",
            self._should_continue,
            {
                "continue": "supervisor_decision",
                "finished": END,
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def _initialize_node(self, state: AgentState) -> AgentState:
        """Initialize the agent and load available tools"""
        try:
            # Initialize MCP client
            await mcp_client.initialize()
            
            # Get available tools
            tools = await mcp_client.get_available_tools()
            
            state["available_tools"] = tools
            state["iteration_count"] = 0
            state["is_finished"] = False
            state["error_message"] = ""
            
            # Add initialization message
            init_msg = AIMessage(content="🚀 Agent initialized with MCP servers and tools loaded")
            state["messages"].append(init_msg)
            
        except Exception as e:
            state["error_message"] = f"Initialization failed: {str(e)}"
            state["is_finished"] = True
        
        return state
    
    async def _supervisor_decision_node(self, state: AgentState) -> AgentState:
        """Supervisor decides which worker to use"""
        try:
            # Convert to supervisor state
            supervisor_state: SupervisorState = {
                "messages": state["messages"],
                "current_task": state["current_task"],
                "available_tools": state["available_tools"],
                "selected_worker": state.get("selected_worker", ""),
                "worker_result": state.get("worker_result", ""),
                "iteration_count": state["iteration_count"],
                "is_finished": state["is_finished"]
            }
            
            # Get supervisor decision
            supervisor_state = await self.supervisor.decide_worker(supervisor_state)
            
            # Update main state
            state["selected_worker"] = supervisor_state["selected_worker"]
            state["current_task"] = supervisor_state["current_task"]
            state["is_finished"] = supervisor_state["is_finished"]
            state["messages"] = supervisor_state["messages"]
            
        except Exception as e:
            state["error_message"] = f"Supervisor decision failed: {str(e)}"
        
        return state
    
    async def _execute_worker_node(self, state: AgentState) -> AgentState:
        """Execute the selected worker"""
        try:
            # Increment iteration count
            state["iteration_count"] += 1
            
            # Check iteration limit
            if state["iteration_count"] > Config.MAX_ITERATIONS:
                state["error_message"] = f"Maximum iterations ({Config.MAX_ITERATIONS}) reached"
                return state
            
            print(f"🔧 Executing worker: {state['selected_worker']}")
            print(f"🔧 Current state keys: {list(state.keys())}")
            
            # Execute worker task
            state = await execute_worker_task(state["selected_worker"], state)
            
            print(f"🔧 Worker result: {state.get('worker_result', 'NO RESULT')}")
            
            # Add worker result to messages
            worker_result = state.get('worker_result', 'No result from worker')
            result_msg = AIMessage(
                content=f"Worker '{state['selected_worker']}' completed task:\n{worker_result}"
            )
            state["messages"].append(result_msg)
            
        except Exception as e:
            print(f"❌ Worker execution error: {e}")
            import traceback
            traceback.print_exc()
            state["error_message"] = f"Worker execution failed: {str(e)}"
        
        return state
    
    async def _evaluate_result_node(self, state: AgentState) -> AgentState:
        """Evaluate the worker result and decide next steps"""
        try:
            # Convert to supervisor state for evaluation
            supervisor_state: SupervisorState = {
                "messages": state["messages"],
                "current_task": state["current_task"],
                "available_tools": state["available_tools"],
                "selected_worker": state["selected_worker"],
                "worker_result": state["worker_result"],
                "iteration_count": state["iteration_count"],
                "is_finished": state["is_finished"]
            }
            
            # Evaluate result
            supervisor_state = await self.supervisor.evaluate_result(supervisor_state)
            
            # Update main state
            state["is_finished"] = supervisor_state["is_finished"]
            state["messages"] = supervisor_state["messages"]
            
        except Exception as e:
            state["error_message"] = f"Result evaluation failed: {str(e)}"
        
        return state
    
    async def _handle_error_node(self, state: AgentState) -> AgentState:
        """Handle errors and provide feedback"""
        error_msg = AIMessage(
            content=f"❌ Error occurred: {state['error_message']}"
        )
        state["messages"].append(error_msg)
        state["is_finished"] = True
        return state
    
    def _should_continue(self, state: AgentState) -> str:
        """Determine the next step in the workflow"""
        if state.get("error_message"):
            return "error"
        elif state.get("is_finished", False):
            return "finished"
        else:
            return "continue"
    
    async def run(self, user_input: str) -> Dict[str, Any]:
        """Run the agent with user input"""
        # Initialize state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "current_task": user_input,
            "available_tools": {},
            "selected_worker": "",
            "worker_result": "",
            "iteration_count": 0,
            "is_finished": False,
            "error_message": ""
        }
        
        try:
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Extract results
            return {
                "success": not bool(final_state.get("error_message")),
                "messages": final_state["messages"],
                "final_result": final_state.get("worker_result", ""),
                "iterations": final_state["iteration_count"],
                "error": final_state.get("error_message", "")
            }
            
        except Exception as e:
            return {
                "success": False,
                "messages": [HumanMessage(content=user_input)],
                "final_result": "",
                "iterations": 0,
                "error": f"Agent execution failed: {str(e)}"
            }
        finally:
            # Clean up MCP connections
            await mcp_client.close()
    
    async def close(self):
        """Close the agent and clean up resources"""
        await mcp_client.close()
