#!/usr/bin/env python3
"""
Chat application runner for the new chat agent
"""

import asyncio
import sys
from typing import Optional
from chat_agent import ChatAgent
from config import Config

class ChatRunner:
    """Main chat application runner"""
    
    def __init__(self):
        self.agent = ChatAgent()
        self.conversation_history = []
    
    async def run_interactive(self):
        """Run the chat agent in interactive mode"""
        print("🤖 Chat Agent Started")
        print("=" * 50)
        print("This is a conversational AI assistant.")
        print("You can ask general questions or request specific actions.")
        print("\nExamples:")
        print("  - 'Hello, how are you?' (general chat)")
        print("  - 'What is machine learning?' (explanations)")
        print("  - 'List files in current directory' (file operations)")
        print("  - 'Search for latest AI news' (web search)")
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
                        print("🔧 (Used tools to complete this request)")
                    
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
        """Run the chat agent for a single message"""
        print(f"🤖 Processing: {message}")
        print("=" * 50)
        
        result = await self.agent.run(message)
        
        if result["success"]:
            print(f"🤖 Response: {result['response']}")
            if result["used_tools"]:
                print("🔧 (Used tools to complete this request)")
        else:
            print(f"❌ Error: {result['error']}")
        
        return result

async def main():
    """Main entry point"""
    runner = ChatRunner()
    
    # Check command line arguments
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
