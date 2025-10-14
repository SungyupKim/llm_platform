#!/usr/bin/env python3
"""
Check what Bedrock models are available
"""

import boto3
from config import Config

def check_available_models():
    """Check what Bedrock models are available"""
    print("🔍 Checking available Bedrock models...")
    
    try:
        # Initialize Bedrock client
        aws_config = Config.get_aws_config()
        aws_config.pop('region_name', None)  # Remove region_name from config
        
        bedrock_client = boto3.client(
            'bedrock',
            region_name=Config.BEDROCK_REGION,
            **aws_config
        )
        
        # List foundation models
        response = bedrock_client.list_foundation_models()
        
        print(f"✅ Found {len(response['modelSummaries'])} available models:")
        print("=" * 60)
        
        for model in response['modelSummaries']:
            model_id = model['modelId']
            provider = model['providerName']
            status = model['modelLifecycle']['status']
            
            print(f"📋 Model: {model_id}")
            print(f"   Provider: {provider}")
            print(f"   Status: {status}")
            print()
        
        # Check specific models we want to use
        target_models = [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-instant-v1",
            "amazon.titan-text-express-v1",
            "meta.llama2-13b-chat-v1"
        ]
        
        print("🎯 Checking specific models we want to use:")
        print("=" * 60)
        
        available_models = [m['modelId'] for m in response['modelSummaries']]
        
        for model_id in target_models:
            if model_id in available_models:
                print(f"✅ {model_id} - AVAILABLE")
            else:
                print(f"❌ {model_id} - NOT AVAILABLE")
        
        # Suggest alternatives
        print("\n💡 Suggestions:")
        print("=" * 60)
        
        claude_models = [m for m in available_models if 'claude' in m.lower()]
        if claude_models:
            print("Available Claude models:")
            for model in claude_models:
                print(f"  - {model}")
        else:
            print("No Claude models available. Consider:")
            print("  1. Request access to Claude models in AWS Bedrock console")
            print("  2. Use alternative models like Amazon Titan or Meta Llama")
            
            titan_models = [m for m in available_models if 'titan' in m.lower()]
            if titan_models:
                print("\nAvailable Titan models:")
                for model in titan_models:
                    print(f"  - {model}")
            
            llama_models = [m for m in available_models if 'llama' in m.lower()]
            if llama_models:
                print("\nAvailable Llama models:")
                for model in llama_models:
                    print(f"  - {model}")
        
    except Exception as e:
        print(f"❌ Error checking models: {e}")
        print("\n💡 This might mean:")
        print("  1. You don't have access to Bedrock")
        print("  2. Your AWS credentials don't have the right permissions")
        print("  3. You need to enable Bedrock in your AWS account")

if __name__ == "__main__":
    check_available_models()
