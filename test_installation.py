#!/usr/bin/env python3
"""
Test script to verify installation and dependencies
"""

def test_imports():
    """Test all required imports"""
    print("🧪 Testing imports...")
    
    try:
        import langgraph
        print("✅ langgraph imported successfully")
    except ImportError as e:
        print(f"❌ langgraph import failed: {e}")
        return False
    
    try:
        import langchain
        print("✅ langchain imported successfully")
    except ImportError as e:
        print(f"❌ langchain import failed: {e}")
        return False
    
    try:
        from langchain_aws.chat_models import ChatBedrock
        print("✅ langchain-aws (ChatBedrock) imported successfully")
    except ImportError:
        try:
            from langchain_aws import ChatBedrock
            print("✅ langchain-aws (alternative) imported successfully")
        except ImportError:
            try:
                from langchain_community.chat_models import BedrockChat
                print("✅ langchain-community (BedrockChat) imported successfully")
            except ImportError as e:
                print(f"❌ All Bedrock imports failed: {e}")
                return False
    
    try:
        import boto3
        print("✅ boto3 imported successfully")
    except ImportError as e:
        print(f"❌ boto3 import failed: {e}")
        return False
    
    try:
        import mcp
        print("✅ mcp imported successfully")
    except ImportError as e:
        print(f"❌ mcp import failed: {e}")
        return False
    
    return True

def test_aws_credentials():
    """Test AWS credentials"""
    print("\n🔐 Testing AWS credentials...")
    
    try:
        import boto3
        from config import Config
        
        aws_config = Config.get_aws_config()
        sts_client = boto3.client('sts', **aws_config)
        identity = sts_client.get_caller_identity()
        print(f"✅ AWS credentials verified for account: {identity.get('Account', 'Unknown')}")
        return True
    except Exception as e:
        print(f"❌ AWS credentials error: {e}")
        return False

def test_bedrock_client():
    """Test Bedrock client initialization"""
    print("\n🤖 Testing Bedrock client...")
    
    try:
        from bedrock_client import bedrock_client
        llm = bedrock_client.get_llm()
        print("✅ Bedrock client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Bedrock client error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 LangGraph MCP Agent - Installation Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test AWS credentials
    if not test_aws_credentials():
        all_passed = False
    
    # Test Bedrock client
    if not test_bedrock_client():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! The system is ready to use.")
        print("\nNext steps:")
        print("1. Run: python test_agent.py")
        print("2. Or run: python main.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Install missing packages: pip install -r requirements.txt")
        print("2. Check AWS credentials in config.py")
        print("3. Ensure you have access to Claude models in AWS Bedrock")

if __name__ == "__main__":
    main()
