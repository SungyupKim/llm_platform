#!/usr/bin/env python3
"""
Test script for the LangGraph MCP Agent
"""

import asyncio
import sys
from langgraph_agent import LangGraphAgent

async def test_agent():
    """Test the agent with various tasks"""
    agent = LangGraphAgent()
    
    test_tasks = [
        "List all files in the current directory",
        "Search for information about Python programming",
        "Create a new file called test.txt with some content",
        "Query the users table in the database"
    ]
    
    print("🧪 Testing LangGraph MCP Agent")
    print("=" * 50)
    
    for i, task in enumerate(test_tasks, 1):
        print(f"\n📋 Test {i}: {task}")
        print("-" * 30)
        
        try:
            result = await agent.run(task)
            
            if result["success"]:
                print(f"✅ Success! Completed in {result['iterations']} iterations")
                if result["final_result"]:
                    print(f"📄 Result: {result['final_result'][:200]}...")
            else:
                print(f"❌ Failed: {result['error']}")
                
        except Exception as e:
            print(f"💥 Exception: {e}")
        
        print()
    
    await agent.close()
    print("🏁 Testing completed!")

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
    
    asyncio.run(test_agent())
