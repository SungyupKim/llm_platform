"""
Bedrock client wrapper with fallback options
"""

import boto3
from typing import Optional, Dict, Any
from config import Config

class BedrockClient:
    """Bedrock client wrapper with multiple import options"""
    
    def __init__(self):
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the LLM with fallback options"""
        
        # Try langchain-aws first
        try:
            from langchain_aws.chat_models import ChatBedrock
            self._create_bedrock_llm(ChatBedrock)
            return
        except ImportError:
            pass
        
        # Try alternative langchain-aws import
        try:
            from langchain_aws import ChatBedrock
            self._create_bedrock_llm(ChatBedrock)
            return
        except ImportError:
            pass
        
        # Try standard langchain bedrock
        try:
            from langchain_community.chat_models import BedrockChat
            self._create_bedrock_llm(BedrockChat)
            return
        except ImportError:
            pass
        
        # Fallback to basic boto3 client
        print("⚠️  Using basic boto3 Bedrock client (limited functionality)")
        self._create_basic_client()
    
    def _create_bedrock_llm(self, ChatBedrockClass):
        """Create Bedrock LLM instance"""
        # Get AWS config without region_name to avoid conflicts
        aws_config = Config.get_aws_config()
        aws_config.pop('region_name', None)  # Remove region_name from config
        
        bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=Config.BEDROCK_REGION,
            **aws_config
        )
        
        self.llm = ChatBedrockClass(
            model_id=Config.SUPERVISOR_MODEL,
            client=bedrock_client,
            model_kwargs={
                "temperature": 0.1,
                "max_tokens": 4000
            }
        )
        print(f"✅ Initialized {ChatBedrockClass.__name__}")
    
    def _create_basic_client(self):
        """Create basic boto3 client as fallback"""
        # Get AWS config without region_name to avoid conflicts
        aws_config = Config.get_aws_config()
        aws_config.pop('region_name', None)  # Remove region_name from config
        
        self.llm = boto3.client(
            'bedrock-runtime',
            region_name=Config.BEDROCK_REGION,
            **aws_config
        )
    
    def get_llm(self):
        """Get the initialized LLM"""
        return self.llm
    
    def create_worker_llm(self):
        """Create a worker-specific LLM instance"""
        # Try langchain-aws first
        try:
            from langchain_aws.chat_models import ChatBedrock
            return self._create_worker_bedrock_llm(ChatBedrock)
        except ImportError:
            pass
        
        try:
            from langchain_aws import ChatBedrock
            return self._create_worker_bedrock_llm(ChatBedrock)
        except ImportError:
            pass
        
        # Fallback to basic client
        return self.llm
    
    def _create_worker_bedrock_llm(self, ChatBedrockClass):
        """Create worker-specific Bedrock LLM"""
        # Get AWS config without region_name to avoid conflicts
        aws_config = Config.get_aws_config()
        aws_config.pop('region_name', None)  # Remove region_name from config
        
        bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=Config.BEDROCK_REGION,
            **aws_config
        )
        
        return ChatBedrockClass(
            model_id=Config.WORKER_MODEL,
            client=bedrock_client,
            model_kwargs={
                "temperature": 0.1,
                "max_tokens": 2000
            }
        )

# Global instance
bedrock_client = BedrockClient()
