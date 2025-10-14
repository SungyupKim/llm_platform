#!/usr/bin/env python3
"""
Main application runner for the LangGraph-based MCP Agent
"""

import asyncio
import sys
from typing import Optional
from langgraph_agent import LangGraphAgent
from config import Config

class AgentRunner:
    """Main application runner"""
    
    def __init__(self):
        self.agent = LangGraphAgent()
    
    async def run_interactive(self):
        """Run the agent in interactive mode"""
        print("🤖 LangGraph MCP Agent Started")
        print("=" * 50)
        print("Available workers:")
        for worker_name in ["filesystem_worker", "search_worker", "database_worker", "aws_worker"]:
            print(f"  - {worker_name}")
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
                
                print("\n🤖 Agent: Processing your request...")
                
                # Run the agent
                result = await self.agent.run(user_input)
                
                # Display results
                if result["success"]:
                    print(f"\n✅ Task completed in {result['iterations']} iterations")
                    if result["final_result"]:
                        print(f"\n📋 Result:\n{result['final_result']}")
                else:
                    print(f"\n❌ Task failed: {result['error']}")
                
                # Show conversation history
                if result["messages"]:
                    print(f"\n💬 Conversation:")
                    for msg in result["messages"][-3:]:  # Show last 3 messages
                        role = "👤 User" if msg.__class__.__name__ == "HumanMessage" else "🤖 Agent"
                        print(f"{role}: {msg.content[:200]}{'...' if len(msg.content) > 200 else ''}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def run_single_task(self, task: str):
        """Run the agent for a single task"""
        print(f"🤖 Running task: {task}")
        print("=" * 50)
        
        result = await self.agent.run(task)
        
        if result["success"]:
            print(f"✅ Task completed in {result['iterations']} iterations")
            if result["final_result"]:
                print(f"\n📋 Result:\n{result['final_result']}")
        else:
            print(f"❌ Task failed: {result['error']}")
        
        return result

async def main():
    """Main entry point"""
    runner = AgentRunner()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        # Single task mode
        task = " ".join(sys.argv[1:])
        await runner.run_single_task(task)
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
        print("   Please check your AWS credentials in config.py")
        sys.exit(1)
    
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
