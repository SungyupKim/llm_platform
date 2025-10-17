#!/usr/bin/env python3
"""
Multi-Database PostgreSQL MCP Server with Write Permissions
This server provides full read/write access to multiple PostgreSQL databases
"""

import asyncio
import json
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional

# Database connections pool
db_connections = {}
current_database = None

def get_db_connection(database_name: str = None):
    """Get database connection for specified database"""
    global db_connections, current_database
    
    # If no database specified, use current database or default
    if not database_name:
        database_name = current_database or "default"
    
    print(f"🔍 get_db_connection called with database_name: {database_name}, current_database: {current_database}")
    
    # Check if connection exists and is still valid
    if database_name in db_connections:
        conn = db_connections[database_name]
        if conn and not conn.closed:
            return conn
    
    # Create new connection
    connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("POSTGRES_CONNECTION_STRING environment variable not set")
    
    # Parse connection string and modify database
    import urllib.parse
    parsed = urllib.parse.urlparse(connection_string)
    
    # Always set the database name dynamically
    if database_name == "default":
        # Use 'postgres' as default database
        database_name = "postgres"
    
    # Create new connection string with the specified database
    new_parsed = parsed._replace(path=f'/{database_name}')
    connection_string = urllib.parse.urlunparse(new_parsed)
    
    try:
        conn = psycopg2.connect(
            connection_string,
            cursor_factory=RealDictCursor
        )
        conn.autocommit = True  # Enable autocommit for write operations
        db_connections[database_name] = conn
        return conn
    except Exception as e:
        raise ValueError(f"Failed to connect to database '{database_name}': {str(e)}")

async def handle_request(request: dict) -> dict:
    """Handle MCP requests"""
    try:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        print(f"🔍 handle_request received: method={method}, params={params}, id={request_id}", file=sys.stderr)
        
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
                        "name": "multi-db-postgres-mcp",
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
                            "name": "list_databases",
                            "description": "List all available databases",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        },
                        {
                            "name": "use_database",
                            "description": "Switch to a specific database",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "database_name": {
                                        "type": "string",
                                        "description": "Name of the database to connect to"
                                    }
                                },
                                "required": ["database_name"]
                            }
                        },
                        {
                            "name": "query",
                            "description": "Execute SQL queries (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, etc.) with full read/write permissions",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "sql": {
                                        "type": "string",
                                        "description": "The SQL query to execute"
                                    },
                                    "database": {
                                        "type": "string",
                                        "description": "Database name (optional, uses current database if not specified)"
                                    }
                                },
                                "required": ["sql"]
                            }
                        },
                        {
                            "name": "list_tables",
                            "description": "List all tables in the current or specified database",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "database": {
                                        "type": "string",
                                        "description": "Database name (optional, uses current database if not specified)"
                                    }
                                },
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
                                    },
                                    "database": {
                                        "type": "string",
                                        "description": "Database name (optional, uses current database if not specified)"
                                    }
                                },
                                "required": ["table_name"]
                            }
                        },
                        {
                            "name": "get_current_database",
                            "description": "Get the name of the currently connected database",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            print(f"🔍 tools/call received: tool_name={tool_name}, arguments={arguments}", file=sys.stderr)
            
            if tool_name == "list_databases":
                result = await list_databases()
            elif tool_name == "use_database":
                # Handle both direct argument and kwargs format
                database_name = arguments.get("database_name") or arguments.get("kwargs", {}).get("database")
                result = use_database(database_name or "")
            elif tool_name == "query":
                result = await execute_query(arguments.get("sql", ""), arguments.get("database"))
            elif tool_name == "list_tables":
                result = await list_tables(arguments.get("database"))
            elif tool_name == "describe_table":
                result = await describe_table(arguments.get("table_name", ""), arguments.get("database"))
            elif tool_name == "get_current_database":
                result = get_current_database()
            else:
                result = f"Unknown tool: {tool_name}"
            
            print(f"🔍 tools/call result: {result}", file=sys.stderr)
            
            # Check if result is already in the correct format
            if isinstance(result, dict) and "content" in result:
                # Result is already in correct format (from use_database, get_current_database)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
            else:
                # Result is a string, wrap it in the correct format
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

async def list_databases() -> str:
    """List all available databases"""
    try:
        conn = get_db_connection()  # Connect to default database
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT datname as database_name, 
                   pg_size_pretty(pg_database_size(datname)) as size
            FROM pg_database 
            WHERE datistemplate = false
            ORDER BY datname
        """)
        
        results = cursor.fetchall()
        cursor.close()
        
        if results:
            db_list = []
            for row in results:
                db_list.append(f"- {row['database_name']} ({row['size']})")
            
            result_text = "Available databases:\n" + "\n".join(db_list)
        else:
            result_text = "No databases found."
        
        return result_text
        
    except Exception as e:
        return f"Error listing databases: {str(e)}"

def use_database(database_name: str) -> dict:
    """Switch to a specific database"""
    global current_database
    
    if not database_name:
        return {"content": [{"type": "text", "text": "Error: Database name is required"}]}
    
    try:
        # Test connection to the database
        conn = get_db_connection(database_name)
        cursor = conn.cursor()
        cursor.execute("SELECT current_database();")
        current_db = cursor.fetchone()['current_database']
        cursor.close()
        
        # Update the current database
        current_database = database_name
        
        return {"content": [{"type": "text", "text": f"Successfully connected to database: {current_db}"}]}
        
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error connecting to database '{database_name}': {str(e)}"}]}

def get_current_database() -> dict:
    """Get the name of the currently connected database"""
    global current_database
    
    if current_database:
        return {"content": [{"type": "text", "text": f"Currently connected to database: {current_database}"}]}
    else:
        return {"content": [{"type": "text", "text": "No database currently selected."}]}

async def execute_query(sql: str, database: str = None) -> str:
    """Execute SQL query with full read/write permissions"""
    if not sql.strip():
        return "Error: Empty SQL query"
    
    try:
        conn = get_db_connection(database)
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

async def list_tables(database: str = None) -> str:
    """List all tables in the current or specified database"""
    try:
        conn = get_db_connection(database)
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

async def describe_table(table_name: str, database: str = None) -> str:
    """Get detailed information about a table structure"""
    if not table_name:
        return "Error: Table name is required"
    
    try:
        conn = get_db_connection(database)
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
    print("🚀 Starting Multi-DB PostgreSQL MCP Server", file=sys.stderr)
    
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
    print("🚀 Multi-DB PostgreSQL MCP Server starting...", file=sys.stderr)
    asyncio.run(main())
