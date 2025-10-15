from typing import Dict, List, Any, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from bedrock_client import bedrock_client
from mcp_client import mcp_client
from config import Config
import json
import re

class ChatState(TypedDict):
    """State for the chat agent"""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    user_input: str
    needs_tools: bool
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    final_response: str
    error_message: str

class ChatAgent:
    """Simple chat agent with conditional tool usage"""
    
    def __init__(self):
        self.llm = bedrock_client.get_llm()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the chat workflow graph"""
        
        workflow = StateGraph(ChatState)
        
        # Add nodes
        workflow.add_node("analyze_input", self._analyze_input_node)
        workflow.add_node("direct_response", self._direct_response_node)
        workflow.add_node("use_tools", self._use_tools_node)
        workflow.add_node("synthesize_response", self._synthesize_response_node)
        
        # Add edges
        workflow.set_entry_point("analyze_input")
        
        # Conditional edge: decide whether to use tools or respond directly
        workflow.add_conditional_edges(
            "analyze_input",
            self._should_use_tools,
            {
                "direct": "direct_response",
                "tools": "use_tools"
            }
        )
        
        workflow.add_edge("direct_response", END)
        workflow.add_edge("use_tools", "synthesize_response")
        workflow.add_edge("synthesize_response", END)
        
        return workflow.compile()
    
    async def _analyze_input_node(self, state: ChatState) -> ChatState:
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
    
    async def _direct_response_node(self, state: ChatState) -> ChatState:
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
    
    async def _use_tools_node(self, state: ChatState) -> ChatState:
        """Use appropriate tools based on user request"""
        user_input = state["user_input"]
        
        # Initialize MCP client if not already done
        try:
            await mcp_client.initialize()
            available_tools = await mcp_client.get_available_tools()
        except Exception as e:
            state["error_message"] = f"Failed to initialize tools: {str(e)}"
            return state
        
        # Create tools description
        tools_description = self._create_tools_description(available_tools)
        
        # Prompt to determine which tools to use
        tool_selection_prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are an AI assistant that selects and uses tools to help users.

Available tools:
{tools_description}

Based on the user's request, determine which tools to use and how to use them. 
Respond with a JSON array of tool calls in this format:
[
    {{
        "server": "server_name",
        "tool": "tool_name", 
        "arguments": {{"param1": "value1", "param2": "value2"}}
    }}
]

Only use tools that are actually available. Be specific with arguments."""),
            ("human", f"User request: {user_input}")
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
                        "result": result
                    })
                except Exception as e:
                    results.append({
                        "server": tool_call["server"],
                        "tool": tool_call["tool"],
                        "error": str(e)
                    })
            
            state["tool_results"] = results
            
        except Exception as e:
            state["error_message"] = f"Tool execution failed: {str(e)}"
        
        return state
    
    async def _synthesize_response_node(self, state: ChatState) -> ChatState:
        """Synthesize final response from tool results"""
        user_input = state["user_input"]
        tool_results = state["tool_results"]
        
        # Create response based on tool results
        results_summary = json.dumps(tool_results, indent=2)
        
        synthesis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI assistant that provides helpful responses based on tool execution results.

Use the tool results to answer the user's request. Present the information in a clear, organized way.
If there were any errors with the tools, mention them but still try to be helpful.

Be conversational and provide context for the results."""),
            ("human", f"User request: {user_input}\n\nTool results:\n{results_summary}")
        ])
        
        try:
            response = await self.llm.ainvoke(synthesis_prompt.format_messages())
            state["final_response"] = response.content
        except Exception as e:
            state["final_response"] = f"I completed the requested action, but encountered an error while formatting the response: {str(e)}"
        
        return state
    
    def _should_use_tools(self, state: ChatState) -> Literal["direct", "tools"]:
        """Determine whether to use tools or respond directly"""
        if state.get("error_message"):
            return "direct"  # Fallback to direct response on error
        
        return "tools" if state.get("needs_tools", False) else "direct"
    
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
            
            # If no valid JSON found, return empty list
            return []
    
    async def run(self, user_input: str, conversation_history: List[BaseMessage] = None) -> Dict[str, Any]:
        """Run the chat agent with user input"""
        if conversation_history is None:
            conversation_history = []
        
        # Initialize state
        initial_state: ChatState = {
            "messages": conversation_history + [HumanMessage(content=user_input)],
            "user_input": user_input,
            "needs_tools": False,
            "tool_calls": [],
            "tool_results": [],
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
                "used_tools": len(final_state.get("tool_calls", [])) > 0,
                "tool_results": final_state.get("tool_results", []),
                "error": final_state.get("error_message", "")
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error: {str(e)}",
                "messages": conversation_history + [HumanMessage(content=user_input)],
                "used_tools": False,
                "tool_results": [],
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
