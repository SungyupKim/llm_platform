#!/usr/bin/env python3
"""
Test script specifically for the supervisor agent
"""

import asyncio
from supervisor import SupervisorAgent, SupervisorState
from langchain_core.messages import HumanMessage

async def test_supervisor():
    """Test the supervisor agent independently"""
    print("🧪 Testing Supervisor Agent")
    print("=" * 40)
    
    supervisor = SupervisorAgent()
    
    # Test cases
    test_cases = [
        "List all files in the current directory",
        "Search for information about Python",
        "Query the users table in the database",
        "Upload a file to S3 bucket"
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case}")
        print("-" * 30)
        
        # Create test state
        state: SupervisorState = {
            "messages": [HumanMessage(content=test_case)],
            "current_task": test_case,
            "available_tools": {
                "filesystem": [{"name": "read_file", "description": "Read a file"}],
                "brave-search": [{"name": "search", "description": "Search the web"}],
                "postgres": [{"name": "query", "description": "Execute SQL"}]
            },
            "selected_worker": "",
            "worker_result": "",
            "iteration_count": 0,
            "is_finished": False
        }
        
        try:
            # Test supervisor decision
            result_state = await supervisor.decide_worker(state)
            
            print(f"✅ Selected worker: {result_state['selected_worker']}")
            print(f"📝 Task description: {result_state['current_task']}")
            print(f"🏁 Is finished: {result_state['is_finished']}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n🏁 Supervisor testing completed!")

if __name__ == "__main__":
    asyncio.run(test_supervisor())
