#!/usr/bin/env python3
"""
Simple PostgreSQL MCP Server with Write Permissions
This server provides full read/write access to PostgreSQL databases
"""

import asyncio
import json
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional

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

async def handle_request(request: dict) -> dict:
    """Handle MCP requests"""
    try:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "simple-postgres-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "query",
                            "description": "Execute SQL queries (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, etc.) with full read/write permissions",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "sql": {
                                        "type": "string",
                                        "description": "The SQL query to execute"
                                    }
                                },
                                "required": ["sql"]
                            }
                        },
                        {
                            "name": "list_tables",
                            "description": "List all tables in the database",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        },
                        {
                            "name": "describe_table",
                            "description": "Get detailed information about a table structure",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "table_name": {
                                        "type": "string",
                                        "description": "Name of the table to describe"
                                    }
                                },
                                "required": ["table_name"]
                            }
                        }
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "query":
                result = await execute_query(arguments.get("sql", ""))
            elif tool_name == "list_tables":
                result = await list_tables()
            elif tool_name == "describe_table":
                result = await describe_table(arguments.get("table_name", ""))
            else:
                result = f"Unknown tool: {tool_name}"
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

async def execute_query(sql: str) -> str:
    """Execute SQL query with full read/write permissions"""
    if not sql.strip():
        return "Error: Empty SQL query"
    
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
        return result_text
        
    except Exception as e:
        return f"Database error: {str(e)}"

async def list_tables() -> str:
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
        
        return result_text
        
    except Exception as e:
        return f"Error listing tables: {str(e)}"

async def describe_table(table_name: str) -> str:
    """Get detailed information about a table structure"""
    if not table_name:
        return "Error: Table name is required"
    
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
        cursor.close()
        
        if not columns:
            return f"Table '{table_name}' not found or has no columns."
        
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
        
        return "\n".join(result_lines)
        
    except Exception as e:
        return f"Error describing table: {str(e)}"

async def main():
    """Main function to run the MCP server"""
    # Test database connection
    try:
        get_db_connection()
        print("✅ Database connection successful", file=sys.stderr)
    except Exception as e:
        print(f"❌ Database connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Read from stdin and write to stdout
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            
            request = json.loads(line.strip())
            response = await handle_request(request)
            print(json.dumps(response))
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
