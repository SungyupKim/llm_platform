#!/usr/bin/env python3
"""
Chain Chat application runner for the chain chat agent
"""

import asyncio
import sys
from typing import Optional
from chain_chat_agent import ChainChatAgent
from config import Config

class ChainChatRunner:
    """Main chain chat application runner"""
    
    def __init__(self, max_tool_iterations: int = 5):
        self.agent = ChainChatAgent(max_tool_iterations)
        self.conversation_history = []
    
    async def run_interactive(self):
        """Run the chain chat agent in interactive mode"""
        print("🤖 Chain Chat Agent Started")
        print("=" * 50)
        print("This is a conversational AI assistant with chained tool support.")
        print("You can ask general questions or request complex multi-step actions.")
        print("\nExamples:")
        print("  - 'Hello, how are you?' (general chat)")
        print("  - 'What is machine learning?' (explanations)")
        print("  - 'List files in current directory' (single tool)")
        print("  - 'Search for latest AI news' (single tool)")
        print("  - 'Find the latest AI news and save it to a file' (chained tools)")
        print("  - 'Search for Python tutorials, then create a summary file' (chained tools)")
        print(f"\nMax tool iterations: {self.agent.max_tool_iterations}")
        print("\nType 'quit' or 'exit' to stop the agent")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("\n🤖 Agent: ", end="", flush=True)
                
                # Run the agent
                result = await self.agent.run(user_input, self.conversation_history)
                
                # Display response
                if result["success"]:
                    print(result["response"])
                    
                    # Show tool usage indicator
                    if result["used_tools"]:
                        print(f"🔧 (Used {result['tool_iterations']} tool iteration(s) to complete this request)")
                        
                        # Show tool chain summary
                        if result["all_tool_results"]:
                            print("\n📋 Tool Chain Summary:")
                            for i, tool_result in enumerate(result["all_tool_results"], 1):
                                server = tool_result.get("server", "unknown")
                                tool = tool_result.get("tool", "unknown")
                                iteration = tool_result.get("iteration", 0)
                                if "error" in tool_result:
                                    print(f"  {i}. [{iteration}] {server}.{tool} ❌ (Error: {tool_result['error']})")
                                else:
                                    print(f"  {i}. [{iteration}] {server}.{tool} ✅")
                    
                    # Update conversation history
                    self.conversation_history = result["messages"]
                else:
                    print(f"❌ Error: {result['error']}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def run_single_message(self, message: str):
        """Run the chain chat agent for a single message"""
        print(f"🤖 Processing: {message}")
        print("=" * 50)
        
        result = await self.agent.run(message)
        
        if result["success"]:
            print(f"🤖 Response: {result['response']}")
            if result["used_tools"]:
                print(f"🔧 (Used {result['tool_iterations']} tool iteration(s) to complete this request)")
                
                # Show tool chain summary
                if result["all_tool_results"]:
                    print("\n📋 Tool Chain Summary:")
                    for i, tool_result in enumerate(result["all_tool_results"], 1):
                        server = tool_result.get("server", "unknown")
                        tool = tool_result.get("tool", "unknown")
                        iteration = tool_result.get("iteration", 0)
                        if "error" in tool_result:
                            print(f"  {i}. [{iteration}] {server}.{tool} ❌ (Error: {tool_result['error']})")
                        else:
                            print(f"  {i}. [{iteration}] {server}.{tool} ✅")
        else:
            print(f"❌ Error: {result['error']}")
        
        return result

async def main():
    """Main entry point"""
    # Parse command line arguments for max iterations
    max_iterations = 5
    if len(sys.argv) > 1 and sys.argv[1].startswith("--max-iterations="):
        try:
            max_iterations = int(sys.argv[1].split("=")[1])
            sys.argv = sys.argv[2:]  # Remove the max-iterations argument
        except ValueError:
            print("Invalid max-iterations value, using default: 5")
    
    runner = ChainChatRunner(max_iterations)
    
    # Check remaining command line arguments
    if len(sys.argv) > 1:
        # Single message mode
        message = " ".join(sys.argv[1:])
        await runner.run_single_message(message)
    else:
        # Interactive mode
        await runner.run_interactive()

if __name__ == "__main__":
    # Check if AWS credentials are configured
    try:
        import boto3
        from config import Config
        # Test AWS credentials
        aws_config = Config.get_aws_config()
        sts_client = boto3.client('sts', **aws_config)
        sts_client.get_caller_identity()
        print("✅ AWS credentials verified")
    except Exception as e:
        print(f"❌ AWS credentials not configured properly: {e}")
        print("   Please check your AWS credentials in .env file")
        sys.exit(1)
    
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
