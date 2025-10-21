#!/usr/bin/env python3
"""
FastMCP MySQL Server - FastMCP를 사용한 MySQL MCP 서버
"""

from fastmcp import FastMCP
import mysql.connector
import os
from typing import List, Dict, Any

# FastMCP 서버 생성
mcp = FastMCP("MySQL Server")

def get_db_connection():
    """데이터베이스 연결 가져오기"""
    connection_string = os.getenv("MYSQL_CONNECTION_STRING", "mysql://test:test@localhost:3306/test")
    # mysql://user:password@host:port/database 형식을 파싱
    parts = connection_string.replace("mysql://", "").split("/")
    auth_host = parts[0]
    database = parts[1] if len(parts) > 1 else "test"
    
    auth, host_port = auth_host.split("@")
    user, password = auth.split(":")
    host, port = host_port.split(":")
    
    return mysql.connector.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database
    )

@mcp.tool()
def list_databases() -> str:
    """List all available databases"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SHOW DATABASES;")
        databases = cursor.fetchall()
        
        if databases:
            db_list = [db[0] for db in databases if db[0] not in ['information_schema', 'performance_schema', 'mysql', 'sys']]
            return f"📊 사용 가능한 데이터베이스:\n" + "\n".join(f"- {db}" for db in db_list)
        else:
            return "📊 데이터베이스가 없습니다."
    
    except Exception as e:
        return f"❌ 데이터베이스 목록 조회 오류: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

@mcp.tool()
def use_database(database_name: str) -> str:
    """Switch to a specific database"""
    try:
        connection_string = os.getenv("MYSQL_CONNECTION_STRING", "mysql://test:test@localhost:3306/test")
        parts = connection_string.replace("mysql://", "").split("/")
        auth_host = parts[0]
        
        auth, host_port = auth_host.split("@")
        user, password = auth.split(":")
        host, port = host_port.split(":")
        
        conn = mysql.connector.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database_name
        )
        conn.close()
        
        return f"✅ 데이터베이스 '{database_name}'로 전환되었습니다."
    
    except Exception as e:
        return f"❌ 데이터베이스 전환 오류: {str(e)}"

@mcp.tool()
def query(sql: str, database: str = None) -> str:
    """Execute SQL queries"""
    try:
        if database:
            connection_string = os.getenv("MYSQL_CONNECTION_STRING", "mysql://test:test@localhost:3306/test")
            parts = connection_string.replace("mysql://", "").split("/")
            auth_host = parts[0]
            
            auth, host_port = auth_host.split("@")
            user, password = auth.split(":")
            host, port = host_port.split(":")
            
            conn = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=database
            )
        else:
            conn = get_db_connection()
        
        cursor = conn.cursor()
        cursor.execute(sql)
        
        if sql.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            if results:
                response = f"📊 쿼리 결과 ({len(results)}개 행):\n\n"
                response += " | ".join(columns) + "\n"
                response += "-" * (len(" | ".join(columns))) + "\n"
                
                for row in results:
                    response += " | ".join(str(cell) for cell in row) + "\n"
                
                return response
            else:
                return "📊 쿼리 결과가 없습니다."
        else:
            conn.commit()
            return f"✅ 쿼리가 성공적으로 실행되었습니다."
    
    except Exception as e:
        return f"❌ 쿼리 실행 오류: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

@mcp.tool()
def list_tables(database: str = None) -> str:
    """List all tables in database"""
    try:
        if database:
            connection_string = os.getenv("MYSQL_CONNECTION_STRING", "mysql://test:test@localhost:3306/test")
            parts = connection_string.replace("mysql://", "").split("/")
            auth_host = parts[0]
            
            auth, host_port = auth_host.split("@")
            user, password = auth.split(":")
            host, port = host_port.split(":")
            
            conn = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=database
            )
        else:
            conn = get_db_connection()
        
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        
        tables = cursor.fetchall()
        
        if tables:
            table_list = [table[0] for table in tables]
            return f"📋 테이블 목록:\n" + "\n".join(f"- {table}" for table in table_list)
        else:
            return "📋 테이블이 없습니다."
    
    except Exception as e:
        return f"❌ 테이블 목록 조회 오류: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

@mcp.tool()
def describe_table(table_name: str, database: str = None) -> str:
    """Get table structure information"""
    try:
        if database:
            connection_string = os.getenv("MYSQL_CONNECTION_STRING", "mysql://test:test@localhost:3306/test")
            parts = connection_string.replace("mysql://", "").split("/")
            auth_host = parts[0]
            
            auth, host_port = auth_host.split("@")
            user, password = auth.split(":")
            host, port = host_port.split(":")
            
            conn = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=database
            )
        else:
            conn = get_db_connection()
        
        cursor = conn.cursor()
        cursor.execute(f"DESCRIBE {table_name};")
        
        columns = cursor.fetchall()
        
        if columns:
            response = f"📋 테이블 '{table_name}' 구조:\n\n"
            response += "컬럼명 | 데이터타입 | NULL 허용 | 키 | 기본값 | Extra\n"
            response += "-" * 60 + "\n"
            
            for col in columns:
                response += f"{col[0]} | {col[1]} | {col[2]} | {col[3]} | {col[4] or 'None'} | {col[5] or 'None'}\n"
            
            return response
        else:
            return f"❌ 테이블 '{table_name}'을 찾을 수 없습니다."
    
    except Exception as e:
        return f"❌ 테이블 구조 조회 오류: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

@mcp.tool()
def get_current_database() -> str:
    """Get the name of currently connected database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DATABASE();")
        current_db = cursor.fetchone()[0]
        
        return f"📊 현재 연결된 데이터베이스: {current_db}"
    
    except Exception as e:
        return f"❌ 현재 데이터베이스 조회 오류: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # SSE 모드로 실행
    mcp.run(transport="sse", port=8012, host="0.0.0.0")
