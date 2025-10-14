# LangGraph MCP Agent

A LangGraph-based agent system that uses the MultiServerMcpClient to manage multiple MCP (Model Context Protocol) servers with a supervisor pattern for tool selection.

## Features

- **Supervisor Pattern**: Intelligent supervisor agent that decides which worker to use for each task
- **MultiServerMcpClient**: Manages multiple MCP servers simultaneously
- **Specialized Workers**: Different workers for different types of tasks:
  - `filesystem_worker`: File operations
  - `search_worker`: Web search operations
  - `database_worker`: Database operations
  - `aws_worker`: AWS service operations
- **LangGraph Workflow**: Robust state management and error handling
- **AWS Bedrock Integration**: Uses Claude 3 models via AWS Bedrock
- **AWS Credentials**: Pre-configured with your AWS credentials

## Setup

1. **Environment Variables**:
   Create a `.env` file in the project root with your AWS credentials:
   ```bash
   # AWS Configuration
   AWS_ACCESS_KEY_ID=your_aws_access_key_here
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
   AWS_REGION=ap-northeast-2
   
   # AWS Bedrock Configuration
   BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
   BEDROCK_REGION=ap-northeast-2
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **AWS Bedrock Setup**:
   The system is pre-configured with your AWS credentials and uses AWS Bedrock with Claude models:
   - **Supervisor**: Claude 3 Sonnet (for complex decision making)
   - **Workers**: Claude 3 Haiku (for faster, cost-effective task execution)
   
   Make sure you have access to these models in your AWS Bedrock console.

3. **Install MCP Servers** (Optional):
   The agent is configured to use these MCP servers:
   - `@modelcontextprotocol/server-filesystem`
   - `@modelcontextprotocol/server-brave-search`
   - `@modelcontextprotocol/server-postgres`

   Install them with:
   ```bash
   npm install -g @modelcontextprotocol/server-filesystem
   npm install -g @modelcontextprotocol/server-brave-search
   npm install -g @modelcontextprotocol/server-postgres
   ```

## Usage

### Interactive Mode
```bash
python main.py
```

### Single Task Mode
```bash
python main.py "List all files in the current directory"
python main.py "Search for information about LangGraph"
python main.py "Create a new file called test.txt"
```

## Architecture

### Supervisor Pattern
The supervisor agent analyzes user requests and decides which specialized worker should handle the task:

1. **Supervisor Decision**: Analyzes the request and selects appropriate worker
2. **Worker Execution**: Selected worker performs the task using MCP tools
3. **Result Evaluation**: Supervisor evaluates the result and decides if task is complete
4. **Iteration**: Process repeats until task is complete or max iterations reached

### MCP Integration
The agent uses `MultiServerMcpClient` to manage multiple MCP servers:

- **Filesystem Server**: File operations (read, write, list, create directories)
- **Search Server**: Web search capabilities
- **Database Server**: PostgreSQL operations
- **AWS Server**: AWS service operations (when configured)

### LangGraph Workflow
The workflow includes these nodes:
- `initialize`: Load MCP servers and tools
- `supervisor_decision`: Decide which worker to use
- `execute_worker`: Run the selected worker
- `evaluate_result`: Check if task is complete
- `handle_error`: Handle any errors

## Configuration

Edit `config.py` to customize:

- **AWS Credentials**: Already configured with your provided keys
- **MCP Servers**: Add/remove MCP server configurations
- **Model Settings**: Change Bedrock models for supervisor/workers
- **Limits**: Adjust maximum iterations and other limits

## Example Tasks

The agent can handle various tasks:

```
# File operations
"Create a new directory called 'projects'"
"Read the contents of config.py"
"List all Python files in the current directory"

# Search operations
"Search for the latest information about LangGraph"
"Find documentation for MCP protocol"

# Database operations (when configured)
"Query the users table"
"Insert a new record into the products table"

# AWS operations (when configured)
"List all S3 buckets"
"Start an EC2 instance"
```

## Error Handling

The agent includes comprehensive error handling:
- MCP server connection failures
- Tool execution errors
- Maximum iteration limits
- Invalid worker selections
- Network timeouts

## Development

To extend the agent:

1. **Add New Workers**: Create new worker classes in `workers.py`
2. **Add MCP Servers**: Configure new servers in `config.py`
3. **Modify Workflow**: Update the LangGraph workflow in `langgraph_agent.py`
4. **Enhance Supervisor**: Improve decision logic in `supervisor.py`

## Troubleshooting

1. **MCP Server Issues**: Ensure MCP servers are installed and accessible
2. **AWS Credentials**: Verify AWS credentials and Bedrock access
3. **Bedrock Model Access**: Ensure you have access to Claude models in your AWS account
4. **Permission Issues**: Check file/directory permissions for filesystem operations
5. **Network Issues**: Ensure internet connectivity for search operations

## License

This project is open source and available under the MIT License.
