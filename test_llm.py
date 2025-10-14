#!/usr/bin/env python3
"""
Test LLM access directly
"""

import asyncio
from bedrock_client import bedrock_client

async def test_llm():
    """Test LLM access directly"""
    print("🧪 Testing LLM Access")
    print("=" * 30)
    
    try:
        llm = bedrock_client.get_llm()
        print(f"✅ LLM initialized: {type(llm)}")
        
        # Test a simple call
        from langchain_core.messages import HumanMessage
        
        response = await llm.ainvoke([HumanMessage(content="Hello, respond with just 'Hi'")])
        print(f"✅ LLM Response: {response.content}")
        
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm())
