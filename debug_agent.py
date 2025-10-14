#!/usr/bin/env python3
"""
Debug version of the agent with detailed logging
"""

import asyncio
import sys
from langgraph_agent import LangGraphAgent

async def debug_single_task(task: str):
    """Debug a single task with detailed logging"""
    print(f"🔍 Debug Mode - Task: {task}")
    print("=" * 50)
    
    agent = LangGraphAgent()
    
    try:
        result = await agent.run(task)
        
        print(f"\n📊 Debug Results:")
        print(f"Success: {result['success']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Error: {result.get('error', 'None')}")
        
        if result['messages']:
            print(f"\n💬 Message History:")
            for i, msg in enumerate(result['messages']):
                role = "👤 User" if msg.__class__.__name__ == "HumanMessage" else "🤖 Agent"
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                print(f"{i+1}. {role}: {content}")
        
        if result['final_result']:
            print(f"\n📋 Final Result:")
            print(result['final_result'])
            
    except Exception as e:
        print(f"💥 Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()

async def main():
    """Main debug function"""
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        await debug_single_task(task)
    else:
        # Default test task
        await debug_single_task("List all files in the current directory")

if __name__ == "__main__":
    asyncio.run(main())
