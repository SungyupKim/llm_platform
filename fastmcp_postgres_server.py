#!/usr/bin/env python3
"""
FastMCP PostgreSQL Server - FastMCP를 사용한 PostgreSQL MCP 서버
"""

from fastmcp import FastMCP
import psycopg2
import os
from typing import List, Dict, Any

# FastMCP 서버 생성
mcp = FastMCP("PostgreSQL Server")

def get_db_connection():
    """데이터베이스 연결 가져오기"""
    connection_string = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
    return psycopg2.connect(connection_string)

@mcp.tool()
def list_databases() -> str:
    """List all available databases"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = cursor.fetchall()
        
        if databases:
            db_list = [db[0] for db in databases]
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
        # 연결 문자열에서 데이터베이스명 변경
        base_connection = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
        new_connection = base_connection.rsplit('/', 1)[0] + f'/{database_name}'
        
        conn = psycopg2.connect(new_connection)
        conn.close()
        
        return f"✅ 데이터베이스 '{database_name}'로 전환되었습니다."
    
    except Exception as e:
        return f"❌ 데이터베이스 전환 오류: {str(e)}"

@mcp.tool()
def query(sql: str, database: str = None) -> str:
    """Execute SQL queries"""
    try:
        if database:
            base_connection = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
            connection_string = base_connection.rsplit('/', 1)[0] + f'/{database}'
        else:
            connection_string = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
        
        conn = psycopg2.connect(connection_string)
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
            base_connection = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
            connection_string = base_connection.rsplit('/', 1)[0] + f'/{database}'
        else:
            connection_string = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
        
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
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
            base_connection = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
            connection_string = base_connection.rsplit('/', 1)[0] + f'/{database}'
        else:
            connection_string = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://test:test@localhost:5432/test")
        
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        
        columns = cursor.fetchall()
        
        if columns:
            response = f"📋 테이블 '{table_name}' 구조:\n\n"
            response += "컬럼명 | 데이터타입 | NULL 허용 | 기본값\n"
            response += "-" * 50 + "\n"
            
            for col in columns:
                response += f"{col[0]} | {col[1]} | {col[2]} | {col[3] or 'None'}\n"
            
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
        
        cursor.execute("SELECT current_database();")
        current_db = cursor.fetchone()[0]
        
        return f"📊 현재 연결된 데이터베이스: {current_db}"
    
    except Exception as e:
        return f"❌ 현재 데이터베이스 조회 오류: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # SSE 모드로 실행
    mcp.run(transport="sse", port=8011, host="0.0.0.0")
