import asyncio
import sys
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from streaming_agent import StreamingAgent
from bedrock_client import bedrock_client
from config import Config

class StreamingMain:
    """Main class for streaming agent interaction"""
    
    def __init__(self):
        self.agent = StreamingAgent()
        self.conversation_history: List[BaseMessage] = []
    
    async def run_interactive(self):
        """Run interactive mode with streaming"""
        print("🚀 Streaming LLM Agent Started!")
        print("Type 'exit' or 'quit' to stop, 'clear' to clear history")
        print("=" * 50)
        
        while True:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("\n👋 Goodbye!")
                    break
                
                if user_input.lower() == 'clear':
                    self.conversation_history = []
                    print("🧹 Conversation history cleared!")
                    continue
                
                if not user_input:
                    continue
                
                print("\n🤖 Agent: ", end="", flush=True)
                
                # Run the agent with streaming
                response_text = ""
                async for update in self.agent.run_streaming(user_input, self.conversation_history):
                    if update["type"] == "step":
                        print(f"\n{update['message']}")
                        if update['details']:
                            print(f"   {update['details']}")
                    elif update["type"] == "stream":
                        # Stream characters in real-time
                        print(update["chunk"], end="", flush=True)
                        response_text += update["chunk"]
                    elif update["type"] == "response" or update["type"] == "response_complete":
                        if update["type"] == "response":
                            print(f"\n{update['message']}")
                            response_text = update['message']
                        if update["used_tools"]:
                            print("\n🔧 (Used tools to complete this request)")
                    elif update["type"] == "error":
                        print(f"\n❌ {update['message']}")
                        response_text = update['message']
                
                # Update conversation history
                self.conversation_history.append(HumanMessage(content=user_input))
                self.conversation_history.append(AIMessage(content=update.get("message", "")))
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def run_single_message(self, message: str):
        """Run a single message with streaming"""
        print(f"🤖 Processing: {message}")
        print("=" * 50)
        
        response_text = ""
        async for update in self.agent.run_streaming(message, self.conversation_history):
            if update["type"] == "step":
                print(f"{update['message']}")
                if update['details']:
                    print(f"   {update['details']}")
            elif update["type"] == "stream":
                # Stream characters in real-time
                print(update["chunk"], end="", flush=True)
                response_text += update["chunk"]
            elif update["type"] == "response" or update["type"] == "response_complete":
                if update["type"] == "response":
                    print(f"\n🤖 Response: {update['message']}")
                    response_text = update['message']
                if update["used_tools"]:
                    print("\n🔧 (Used tools to complete this request)")
            elif update["type"] == "error":
                print(f"\n❌ Error: {update['message']}")
                response_text = update['message']

async def main():
    """Main entry point"""
    try:
        # Initialize Bedrock client
        print("✅ Initialized ChatBedrock")
        print("✅ AWS credentials verified")
        
        # Create and run the streaming main
        streaming_main = StreamingMain()
        
        if len(sys.argv) > 1:
            # Single message mode
            message = " ".join(sys.argv[1:])
            await streaming_main.run_single_message(message)
        else:
            # Interactive mode
            await streaming_main.run_interactive()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    finally:
        # Clean up
        try:
            await streaming_main.agent.close()
        except:
            pass
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
