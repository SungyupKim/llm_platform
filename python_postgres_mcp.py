#!/usr/bin/env python3
"""
Python PostgreSQL MCP Server with Write Permissions
This server provides full read/write access to PostgreSQL databases
"""

import asyncio
import json
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Initialize the MCP server
server = Server("python-postgres-mcp")

# Database connection
db_connection = None

def get_db_connection():
    """Get database connection using environment variable"""
    global db_connection
    if db_connection is None or db_connection.closed:
        connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("POSTGRES_CONNECTION_STRING environment variable not set")
        
        db_connection = psycopg2.connect(
            connection_string,
            cursor_factory=RealDictCursor
        )
        db_connection.autocommit = True  # Enable autocommit for write operations
    return db_connection

@server.list_tools()
async def list_tools() -> ListToolsResult:
    """List available tools"""
    return ListToolsResult(
        tools=[
            Tool(
                name="query",
                description="Execute SQL queries (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, etc.) with full read/write permissions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL query to execute"
                        }
                    },
                    "required": ["sql"]
                }
            ),
            Tool(
                name="list_tables",
                description="List all tables in the database",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="describe_table",
                description="Get detailed information about a table structure",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Name of the table to describe"
                        }
                    },
                    "required": ["table_name"]
                }
            ),
            Tool(
                name="get_table_data",
                description="Get data from a table with optional limit and offset",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Name of the table"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return (default: 100)",
                            "default": 100
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Number of rows to skip (default: 0)",
                            "default": 0
                        },
                        "where_clause": {
                            "type": "string",
                            "description": "Optional WHERE clause (without WHERE keyword)"
                        }
                    },
                    "required": ["table_name"]
                }
            )
        ]
    )

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls"""
    try:
        if name == "query":
            return await execute_query(arguments.get("sql", ""))
        elif name == "list_tables":
            return await list_tables()
        elif name == "describe_table":
            return await describe_table(arguments.get("table_name", ""))
        elif name == "get_table_data":
            return await get_table_data(
                arguments.get("table_name", ""),
                arguments.get("limit", 100),
                arguments.get("offset", 0),
                arguments.get("where_clause", "")
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")]
            )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}", meta=None)]
        )

async def execute_query(sql: str) -> CallToolResult:
    """Execute SQL query with full read/write permissions"""
    if not sql.strip():
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Empty SQL query", meta=None)]
        )
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute the query
        cursor.execute(sql)
        
        # Check if it's a SELECT query
        if sql.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            if results:
                # Convert results to JSON-serializable format
                json_results = []
                for row in results:
                    json_results.append(dict(row))
                
                result_text = json.dumps(json_results, indent=2, default=str)
            else:
                result_text = "Query executed successfully. No rows returned."
        else:
            # For non-SELECT queries (INSERT, UPDATE, DELETE, etc.)
            affected_rows = cursor.rowcount
            result_text = f"Query executed successfully. {affected_rows} row(s) affected."
        
        cursor.close()
        
        return CallToolResult(
            content=[TextContent(type="text", text=result_text, meta=None)]
        )
        
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Database error: {str(e)}")]
        )

async def list_tables() -> CallToolResult:
    """List all tables in the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name, table_type
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        results = cursor.fetchall()
        cursor.close()
        
        if results:
            table_list = []
            for row in results:
                table_list.append(f"- {row['table_name']} ({row['table_type']})")
            
            result_text = "Tables in the database:\n" + "\n".join(table_list)
        else:
            result_text = "No tables found in the database."
        
        return CallToolResult(
            content=[TextContent(type="text", text=result_text, meta=None)]
        )
        
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error listing tables: {str(e)}")]
        )

async def describe_table(table_name: str) -> CallToolResult:
    """Get detailed information about a table structure"""
    if not table_name:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Table name is required", meta=None)]
        )
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get column information
        cursor.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        
        # Get constraints
        cursor.execute("""
            SELECT 
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = %s AND tc.table_schema = 'public'
        """, (table_name,))
        
        constraints = cursor.fetchall()
        cursor.close()
        
        if not columns:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Table '{table_name}' not found or has no columns.")]
            )
        
        # Format the result
        result_lines = [f"Table: {table_name}", "=" * 50, ""]
        
        result_lines.append("Columns:")
        for col in columns:
            col_info = f"  - {col['column_name']}: {col['data_type']}"
            if col['character_maximum_length']:
                col_info += f"({col['character_maximum_length']})"
            if col['is_nullable'] == 'NO':
                col_info += " NOT NULL"
            if col['column_default']:
                col_info += f" DEFAULT {col['column_default']}"
            result_lines.append(col_info)
        
        if constraints:
            result_lines.append("\nConstraints:")
            for constraint in constraints:
                result_lines.append(f"  - {constraint['constraint_name']}: {constraint['constraint_type']} on {constraint['column_name']}")
        
        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(result_lines))]
        )
        
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error describing table: {str(e)}")]
        )

async def get_table_data(table_name: str, limit: int = 100, offset: int = 0, where_clause: str = "") -> CallToolResult:
    """Get data from a table with optional filtering"""
    if not table_name:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Table name is required", meta=None)]
        )
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build the query
        query = f"SELECT * FROM {table_name}"
        params = []
        
        if where_clause:
            query += f" WHERE {where_clause}"
        
        query += f" LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        
        if results:
            # Convert results to JSON-serializable format
            json_results = []
            for row in results:
                json_results.append(dict(row))
            
            result_text = json.dumps(json_results, indent=2, default=str)
        else:
            result_text = f"No data found in table '{table_name}' with the given criteria."
        
        return CallToolResult(
            content=[TextContent(type="text", text=result_text, meta=None)]
        )
        
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error getting table data: {str(e)}")]
        )

async def main():
    """Main function to run the MCP server"""
    # Test database connection
    try:
        get_db_connection()
        print("✅ Database connection successful", file=sys.stderr)
    except Exception as e:
        print(f"❌ Database connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
