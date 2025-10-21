# 🚀 FastMCP Servers

FastMCP를 사용하여 구현된 SSE(Server-Sent Events) 기반 MCP 서버들입니다.

## 📋 서버 목록

| 서버 | 포트 | 설명 | 도구 |
|------|------|------|------|
| **Calculator** | 8009 | 수학 계산 | `add`, `multiply`, `divide` |
| **RAG** | 8010 | 문서 처리 및 검색 | `rag_upload_pdf`, `rag_search`, `rag_chat`, `rag_get_info` |
| **PostgreSQL** | 8011 | PostgreSQL 데이터베이스 작업 | `list_databases`, `use_database`, `query`, `list_tables`, `describe_table`, `get_current_database` |
| **MySQL** | 8012 | MySQL 데이터베이스 작업 | `list_databases`, `use_database`, `query`, `list_tables`, `describe_table`, `get_current_database` |

## 🚀 서버 실행

```bash
# 각 서버를 개별적으로 실행
python3 fastmcp_calculator_server.py    # 포트 8009
python3 fastmcp_rag_server.py           # 포트 8010
python3 fastmcp_postgres_server.py      # 포트 8011
python3 fastmcp_mysql_server.py         # 포트 8012
```

## 📡 FastMCP SSE 엔드포인트

FastMCP는 자체 SSE 엔드포인트를 제공합니다:

### 1. Calculator Server (포트 8009)
- **SSE 엔드포인트**: `http://0.0.0.0:8009/sse`
- **도구**: `add`, `multiply`, `divide`

### 2. RAG Server (포트 8010)
- **SSE 엔드포인트**: `http://0.0.0.0:8010/sse`
- **도구**: `rag_upload_pdf`, `rag_search`, `rag_chat`, `rag_get_info`

### 3. PostgreSQL Server (포트 8011)
- **SSE 엔드포인트**: `http://0.0.0.0:8011/sse`
- **도구**: `list_databases`, `use_database`, `query`, `list_tables`, `describe_table`, `get_current_database`

### 4. MySQL Server (포트 8012)
- **SSE 엔드포인트**: `http://0.0.0.0:8012/sse`
- **도구**: `list_databases`, `use_database`, `query`, `list_tables`, `describe_table`, `get_current_database`

## 🔧 FastMCP 클라이언트 사용법

### Python 클라이언트

```python
import httpx
import json

async def call_fastmcp_tool(server_url: str, tool_name: str, **kwargs):
    """FastMCP 서버의 도구 호출"""
    async with httpx.AsyncClient() as client:
        # SSE 연결
        async with client.stream('GET', f"{server_url}/sse") as response:
            # MCP 요청 전송
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": kwargs
                }
            }
            
            # 요청 전송 (POST)
            await client.post(f"{server_url}/sse", json=request)
            
            # SSE 응답 수신
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    yield data

# 사용 예시
async def main():
    async for event in call_fastmcp_tool('http://localhost:8009', 'add', a=10, b=5):
        print(f"Received: {event}")
```

### JavaScript 클라이언트

```javascript
class FastMCPClient {
    constructor(serverUrl) {
        this.serverUrl = serverUrl;
    }
    
    async callTool(toolName, arguments) {
        const eventSource = new EventSource(`${this.serverUrl}/sse`);
        
        // MCP 요청 전송
        const request = {
            jsonrpc: "2.0",
            id: 1,
            method: "tools/call",
            params: {
                name: toolName,
                arguments: arguments
            }
        };
        
        // POST 요청으로 도구 호출
        await fetch(`${this.serverUrl}/sse`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request)
        });
        
        // SSE 응답 처리
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
        };
        
        return eventSource;
    }
}

// 사용 예시
const client = new FastMCPClient('http://localhost:8009');
client.callTool('add', {a: 10, b: 5});
```

## 🌐 웹 브라우저에서 사용

```html
<!DOCTYPE html>
<html>
<head>
    <title>FastMCP Client</title>
</head>
<body>
    <div id="result"></div>
    
    <script>
        async function callCalculator() {
            const eventSource = new EventSource('http://localhost:8009/sse');
            
            // MCP 요청 전송
            const request = {
                jsonrpc: "2.0",
                id: 1,
                method: "tools/call",
                params: {
                    name: "add",
                    arguments: {a: 10, b: 5}
                }
            };
            
            await fetch('http://localhost:8009/sse', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(request)
            });
            
            // SSE 응답 처리
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                document.getElementById('result').innerHTML += 
                    `<p>${JSON.stringify(data)}</p>`;
            };
        }
        
        callCalculator();
    </script>
</body>
</html>
```

## 🔒 보안 및 설정

### 환경 변수

각 서버는 다음 환경 변수를 사용합니다:

**PostgreSQL Server:**
```bash
export POSTGRES_CONNECTION_STRING="postgresql://user:password@localhost:5432/database"
```

**MySQL Server:**
```bash
export MYSQL_CONNECTION_STRING="mysql://user:password@localhost:3306/database"
```

**RAG Server:**
```bash
export AWS_REGION="ap-northeast-2"
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
```

### 네트워크 설정

- 모든 서버는 `0.0.0.0`에 바인딩되어 외부 접근 가능
- CORS가 기본적으로 활성화됨
- 프로덕션 환경에서는 적절한 보안 설정 필요

## 🚀 장점

1. **FastMCP 네이티브**: FastMCP의 내장 SSE 기능 활용
2. **자동 문서화**: FastMCP가 자동으로 API 문서 생성
3. **타입 안전성**: Pydantic을 통한 타입 검증
4. **실시간 스트리밍**: SSE를 통한 실시간 응답
5. **원격 호출**: HTTP로 다른 서버에서 호출 가능
6. **웹 호환**: 브라우저에서 직접 사용 가능

## 📝 사용 예시

### 계산기 서버 테스트

```bash
# 브라우저에서 접속
http://localhost:8009/sse

# 또는 curl로 테스트
curl -X POST http://localhost:8009/sse \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "add",
      "arguments": {"a": 10, "b": 5}
    }
  }'
```

### RAG 서버 테스트

```bash
# 문서 검색
curl -X POST http://localhost:8010/sse \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "rag_chat",
      "arguments": {"question": "test", "n_results": 3}
    }
  }'
```

---

**🎉 FastMCP를 사용한 SSE 기반 MCP 서버들이 준비되었습니다!**


