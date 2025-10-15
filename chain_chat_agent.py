from typing import Dict, List, Any, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from bedrock_client import bedrock_client
from mcp_client import mcp_client
from config import Config
import json
import re

class ChainChatState(TypedDict):
    """State for the chain chat agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    user_input: str
    needs_tools: bool
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    all_tool_results: List[Dict[str, Any]]  # Accumulate all results
    iteration_count: int
    max_iterations: int
    final_response: str
    error_message: str

class ChainChatAgent:
    """Chat agent with support for chained tool calls"""
    
    def __init__(self, max_tool_iterations: int = 5):
        self.llm = bedrock_client.get_llm()
        self.max_tool_iterations = max_tool_iterations
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the chain chat workflow graph"""
        
        workflow = StateGraph(ChainChatState)
        
        # Add nodes
        workflow.add_node("analyze_input", self._analyze_input_node)
        workflow.add_node("direct_response", self._direct_response_node)
        workflow.add_node("tool_chain", self._tool_chain_node)
        workflow.add_node("evaluate_tool_results", self._evaluate_tool_results_node)
        workflow.add_node("synthesize_final_response", self._synthesize_final_response_node)
        
        # Add edges
        workflow.set_entry_point("analyze_input")
        
        # Conditional edge: decide whether to use tools or respond directly
        workflow.add_conditional_edges(
            "analyze_input",
            self._should_use_tools,
            {
                "direct": "direct_response",
                "tools": "tool_chain"
            }
        )
        
        workflow.add_edge("direct_response", END)
        
        # Tool chain loop
        workflow.add_conditional_edges(
            "tool_chain",
            self._should_continue_tool_chain,
            {
                "continue": "evaluate_tool_results",
                "synthesize": "synthesize_final_response"
            }
        )
        
        workflow.add_conditional_edges(
            "evaluate_tool_results",
            self._should_continue_tool_chain,
            {
                "continue": "tool_chain",
                "synthesize": "synthesize_final_response"
            }
        )
        
        workflow.add_edge("synthesize_final_response", END)
        
        return workflow.compile()
    
    async def _analyze_input_node(self, state: ChainChatState) -> ChainChatState:
        """Analyze user input to determine if tools are needed"""
        user_input = state["user_input"]
        
        # Create prompt to analyze if tools are needed
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI assistant that analyzes user requests to determine if tools are needed.

Available tools:
- File operations (read, write, list files/directories)
- Web search (search for information online)
- Database operations (query, insert, update data)
- AWS operations (S3, EC2, Lambda, etc.)

Analyze the user's request and respond with ONLY one of these options:
- "direct": For general conversation, questions, explanations, or simple responses
- "tools": For requests that require file operations, web search, database access, or AWS services

Examples:
- "Hello, how are you?" → direct
- "What is Python?" → direct
- "List files in current directory" → tools
- "Search for latest AI news" → tools
- "Create a new file" → tools
- "Explain machine learning" → direct
- "Find the latest AI news and save it to a file" → tools (chained operations)

Respond with only: direct OR tools"""),
            ("human", f"User request: {user_input}")
        ])
        
        try:
            response = await self.llm.ainvoke(analysis_prompt.format_messages())
            decision = response.content.strip().lower()
            
            if "tools" in decision:
                state["needs_tools"] = True
            else:
                state["needs_tools"] = False
                
        except Exception as e:
            print(f"❌ Analysis error: {e}")
            # Default to direct response on error
            state["needs_tools"] = False
        
        return state
    
    async def _direct_response_node(self, state: ChainChatState) -> ChainChatState:
        """Generate direct response without tools"""
        user_input = state["user_input"]
        conversation_history = state["messages"][:-1]  # Exclude the current user message
        
        # Create conversation context
        context_messages = []
        for msg in conversation_history[-6:]:  # Keep last 6 messages for context
            if isinstance(msg, HumanMessage):
                context_messages.append(("human", msg.content))
            elif isinstance(msg, AIMessage):
                context_messages.append(("assistant", msg.content))
        
        # Add current user message
        context_messages.append(("human", user_input))
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful AI assistant. Provide clear, accurate, and helpful responses to user questions and requests. 
            
If the user asks about something that would require tools (like file operations, web search, etc.), politely explain that you can help with general questions and explanations, but for specific actions they would need to use the appropriate tools.

Be conversational, friendly, and informative."""),
            *context_messages
        ])
        
        try:
            response = await self.llm.ainvoke(prompt.format_messages())
            state["final_response"] = response.content
        except Exception as e:
            state["final_response"] = f"I apologize, but I encountered an error while processing your request: {str(e)}"
        
        return state
    
    async def _tool_chain_node(self, state: ChainChatState) -> ChainChatState:
        """Execute tool calls in the chain"""
        user_input = state["user_input"]
        previous_results = state.get("all_tool_results", [])
        
        # Initialize MCP client if not already done
        try:
            await mcp_client.initialize()
            available_tools = await mcp_client.get_available_tools()
        except Exception as e:
            state["error_message"] = f"Failed to initialize tools: {str(e)}"
            return state
        
        # Create tools description (escape braces to avoid formatting issues)
        tools_description = self._create_tools_description(available_tools).replace("{", "{{").replace("}", "}}")
        
        # Create context from previous results
        context = ""
        if previous_results:
            # Escape braces in JSON to avoid formatting issues
            context_json = json.dumps(previous_results, indent=2).replace("{", "{{").replace("}", "}}")
            context = f"\n\nPrevious tool results:\n{context_json}"
        
        # Simple prompt without complex formatting
        system_message = """You are an AI assistant that selects and uses tools to help users.

Available tools:
- filesystem: read_file, write_file, list_directory, create_directory
- brave-search: search, search_news  
- postgres: query, list_tables, describe_table

Based on the user's request, determine which tools to use.
Respond with a JSON array of tool calls in this format:
[
    {
        "server": "server_name",
        "tool": "tool_name", 
        "arguments": {"param1": "value1", "param2": "value2"}
    }
]

If no tools are needed, respond with an empty array: []"""

        human_message = f"User request: {user_input}{context}"
        
        tool_selection_prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", human_message)
        ])
        
        try:
            response = await self.llm.ainvoke(tool_selection_prompt.format_messages())
            
            # Parse tool calls from response
            tool_calls = self._parse_tool_calls(response.content)
            state["tool_calls"] = tool_calls
            
            # Execute tool calls
            results = []
            for tool_call in tool_calls:
                try:
                    result = await mcp_client.call_tool(
                        tool_call["server"],
                        tool_call["tool"],
                        tool_call["arguments"]
                    )
                    results.append({
                        "server": tool_call["server"],
                        "tool": tool_call["tool"],
                        "arguments": tool_call["arguments"],
                        "reasoning": tool_call.get("reasoning", ""),
                        "result": result,
                        "iteration": state["iteration_count"]
                    })
                except Exception as e:
                    results.append({
                        "server": tool_call["server"],
                        "tool": tool_call["tool"],
                        "arguments": tool_call["arguments"],
                        "reasoning": tool_call.get("reasoning", ""),
                        "error": str(e),
                        "iteration": state["iteration_count"]
                    })
            
            state["tool_results"] = results
            
            # Add to accumulated results
            if "all_tool_results" not in state:
                state["all_tool_results"] = []
            state["all_tool_results"].extend(results)
            
        except Exception as e:
            print(f"❌ Tool execution error details: {e}")
            import traceback
            traceback.print_exc()
            state["error_message"] = f"Tool execution failed: {str(e)}"
        
        return state
    
    async def _evaluate_tool_results_node(self, state: ChainChatState) -> ChainChatState:
        """Evaluate tool results and decide if more tools are needed"""
        user_input = state["user_input"]
        all_results = state.get("all_tool_results", [])
        
        # Create summary of all results so far
        results_summary = json.dumps(all_results, indent=2)
        
        evaluation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI assistant that evaluates tool execution results to determine if more tools are needed.

Based on the user's original request and the results from tools executed so far, decide if:
1. More tools are needed to complete the task
2. The task is complete and ready for final response

Consider:
- Has the user's request been fully satisfied?
- Are there any follow-up actions needed?
- Do the results provide enough information?

Respond with ONLY one of these options:
- "continue": More tools are needed
- "complete": Task is complete, ready for final response"""),
            ("human", f"Original user request: {user_input}\n\nTool results so far:\n{results_summary}")
        ])
        
        try:
            response = await self.llm.ainvoke(evaluation_prompt.format_messages())
            decision = response.content.strip().lower()
            
            if "complete" in decision:
                state["needs_tools"] = False
            else:
                state["needs_tools"] = True
                
        except Exception as e:
            print(f"❌ Evaluation error: {e}")
            # Default to complete on error
            state["needs_tools"] = False
        
        return state
    
    async def _synthesize_final_response_node(self, state: ChainChatState) -> ChainChatState:
        """Synthesize final response from all tool results"""
        user_input = state["user_input"]
        all_results = state.get("all_tool_results", [])
        
        # Create response based on all tool results
        results_summary = json.dumps(all_results, indent=2)
        
        synthesis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI assistant that provides helpful responses based on tool execution results.

Use all the tool results to answer the user's request. Present the information in a clear, organized way.
If there were any errors with the tools, mention them but still try to be helpful.

Be conversational and provide context for the results. If multiple tools were used, explain the sequence of actions taken."""),
            ("human", f"User request: {user_input}\n\nAll tool results:\n{results_summary}")
        ])
        
        try:
            response = await self.llm.ainvoke(synthesis_prompt.format_messages())
            state["final_response"] = response.content
        except Exception as e:
            state["final_response"] = f"I completed the requested actions, but encountered an error while formatting the response: {str(e)}"
        
        return state
    
    def _should_use_tools(self, state: ChainChatState) -> Literal["direct", "tools"]:
        """Determine whether to use tools or respond directly"""
        if state.get("error_message"):
            return "direct"  # Fallback to direct response on error
        
        return "tools" if state.get("needs_tools", False) else "direct"
    
    def _should_continue_tool_chain(self, state: ChainChatState) -> Literal["continue", "synthesize"]:
        """Determine whether to continue the tool chain or synthesize response"""
        if state.get("error_message"):
            return "synthesize"  # End chain on error
        
        # Check iteration limit
        if state["iteration_count"] >= state["max_iterations"]:
            print(f"🔄 Reached maximum iterations ({state['max_iterations']})")
            return "synthesize"
        
        # Check if more tools are needed
        if state.get("needs_tools", False):
            return "continue"
        else:
            return "synthesize"
    
    def _create_tools_description(self, available_tools: Dict[str, List[Dict[str, Any]]]) -> str:
        """Create a description of available tools"""
        description = ""
        for server_name, tools in available_tools.items():
            description += f"\n{server_name.upper()}:\n"
            for tool in tools:
                description += f"  - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}\n"
        return description
    
    def _parse_tool_calls(self, response_content: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response"""
        try:
            # Try to parse as JSON first
            parsed = json.loads(response_content)
            if isinstance(parsed, list):
                return parsed
            else:
                return [parsed]
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            json_patterns = [
                r'\[.*?\]',  # Array pattern
                r'\{.*?\}',  # Object pattern
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response_content, re.DOTALL)
                for match in matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, list):
                            return parsed
                        else:
                            return [parsed]
                    except json.JSONDecodeError:
                        continue
            
            # If no valid JSON found, create default tool call based on common patterns
            response_lower = response_content.lower()
            if any(keyword in response_lower for keyword in ["list", "ls", "directory", "files"]):
                return [{
                    "server": "filesystem",
                    "tool": "list_directory",
                    "arguments": {"path": "."}
                }]
            elif any(keyword in response_lower for keyword in ["search", "find", "web"]):
                return [{
                    "server": "brave-search",
                    "tool": "search",
                    "arguments": {"query": "general search"}
                }]
            else:
                return []
    
    async def run(self, user_input: str, conversation_history: List[BaseMessage] = None) -> Dict[str, Any]:
        """Run the chain chat agent with user input"""
        if conversation_history is None:
            conversation_history = []
        
        # Initialize state
        initial_state: ChainChatState = {
            "messages": conversation_history + [HumanMessage(content=user_input)],
            "user_input": user_input,
            "needs_tools": False,
            "tool_calls": [],
            "tool_results": [],
            "all_tool_results": [],
            "iteration_count": 0,
            "max_iterations": self.max_tool_iterations,
            "final_response": "",
            "error_message": ""
        }
        
        try:
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Add the final response to messages
            final_state["messages"].append(AIMessage(content=final_state["final_response"]))
            
            return {
                "success": not bool(final_state.get("error_message")),
                "response": final_state["final_response"],
                "messages": final_state["messages"],
                "used_tools": len(final_state.get("all_tool_results", [])) > 0,
                "tool_iterations": final_state["iteration_count"],
                "all_tool_results": final_state.get("all_tool_results", []),
                "error": final_state.get("error_message", "")
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error: {str(e)}",
                "messages": conversation_history + [HumanMessage(content=user_input)],
                "used_tools": False,
                "tool_iterations": 0,
                "all_tool_results": [],
                "error": f"Agent execution failed: {str(e)}"
            }
        finally:
            # Clean up MCP connections
            try:
                await mcp_client.close()
            except:
                pass
    
    async def close(self):
        """Close the agent and clean up resources"""
        await mcp_client.close()
