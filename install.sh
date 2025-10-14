#!/bin/bash

echo "🚀 Installing LangGraph MCP Agent Dependencies"
echo "=============================================="

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install -r requirements.txt

# Check if langchain-aws is properly installed
echo "🔍 Verifying langchain-aws installation..."
python -c "from langchain_aws.chat_models import ChatBedrock; print('✅ langchain-aws installed successfully')" 2>/dev/null || {
    echo "❌ langchain-aws not found, trying alternative installation..."
    pip install --upgrade langchain-aws
}

# Test AWS credentials
echo "🔐 Testing AWS credentials..."
python -c "
import boto3
from config import Config
try:
    sts_client = boto3.client('sts', **Config.get_aws_config())
    identity = sts_client.get_caller_identity()
    print(f'✅ AWS credentials verified for account: {identity.get(\"Account\", \"Unknown\")}')
except Exception as e:
    print(f'❌ AWS credentials error: {e}')
    print('Please check your AWS credentials in config.py')
"

echo "🎉 Installation completed!"
echo ""
echo "Next steps:"
echo "1. Make sure you have access to Claude models in AWS Bedrock"
echo "2. Run: python test_agent.py"
echo "3. Or run: python main.py"
