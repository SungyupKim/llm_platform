import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the LLM Agent"""
    
    # AWS Configuration - Load from environment variables
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
    
    # AWS Bedrock Configuration - Load from environment variables
    BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")
    BEDROCK_REGION = os.getenv("BEDROCK_REGION", "ap-northeast-2")
    
    # MCP Server Configuration
    MCP_SERVERS = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/ubuntu/llm_agent"]
        },
        "brave-search": {
            "command": "npx", 
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {
                "BRAVE_API_KEY": "your_brave_api_key_here"
            }
        },
        "postgres": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres"],
            "env": {
                "POSTGRES_CONNECTION_STRING": "postgresql://user:password@localhost:5432/dbname"
            }
        }
    }
    
    # Agent Configuration
    MAX_ITERATIONS = 10
    SUPERVISOR_MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"  # Claude 3.5 Sonnet for supervisor
    WORKER_MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"  # Claude 3.5 Sonnet for workers
    
    @classmethod
    def get_aws_config(cls) -> Dict[str, str]:
        """Get AWS configuration for boto3"""
        return {
            "aws_access_key_id": cls.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": cls.AWS_SECRET_ACCESS_KEY,
            "region_name": cls.AWS_REGION
        }
