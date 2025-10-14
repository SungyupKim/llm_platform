#!/usr/bin/env python3
"""
Script to help request model access in AWS Bedrock
"""

import boto3
from config import Config

def request_model_access():
    """Request access to Bedrock models"""
    print("🔐 Requesting Model Access in AWS Bedrock")
    print("=" * 50)
    
    try:
        # Initialize Bedrock client
        aws_config = Config.get_aws_config()
        aws_config.pop('region_name', None)
        
        bedrock_client = boto3.client(
            'bedrock',
            region_name=Config.BEDROCK_REGION,
            **aws_config
        )
        
        # List models that require access
        models_to_request = [
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0"
        ]
        
        print("📋 Models you need to request access for:")
        for model in models_to_request:
            print(f"  - {model}")
        
        print("\n🌐 To request access:")
        print("1. Go to AWS Bedrock Console: https://console.aws.amazon.com/bedrock/")
        print("2. Click on 'Model access' in the left sidebar")
        print("3. Click 'Request model access'")
        print("4. Select the models above")
        print("5. Submit the request")
        print("6. Wait for approval (usually takes a few minutes)")
        
        print("\n💡 Alternative: Use models that don't require access:")
        print("  - amazon.titan-text-express-v1")
        print("  - amazon.titan-text-lite-v1")
        print("  - meta.llama3-8b-instruct-v1:0")
        
        # Check current access
        print("\n🔍 Checking current model access...")
        try:
            response = bedrock_client.list_foundation_models()
            accessible_models = []
            
            for model in response['modelSummaries']:
                if model['modelId'] in models_to_request:
                    accessible_models.append(model['modelId'])
            
            if accessible_models:
                print("✅ You have access to these models:")
                for model in accessible_models:
                    print(f"  - {model}")
            else:
                print("❌ You don't have access to any of the requested models yet")
                
        except Exception as e:
            print(f"⚠️  Could not check model access: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Make sure:")
        print("1. Your AWS credentials are correct")
        print("2. You have permission to access Bedrock")
        print("3. Bedrock is enabled in your AWS account")

if __name__ == "__main__":
    request_model_access()
