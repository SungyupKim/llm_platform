# MySQL & PostgreSQL MCP 서버 Docker 가이드

이 가이드는 MySQL과 PostgreSQL MCP 서버를 Docker로 빌드하고 실행하는 방법을 설명합니다.

## 📁 프로젝트 구조

```
llm_agent/
├── mysql-mcp/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── fastmcp_mysql_server.py
├── postgres-mcp/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── fastmcp_postgres_server.py
├── docker-compose.yml
└── DOCKER_GUIDE.md
```

## 🚀 빠른 시작

### 1. MCP 서버만 실행 (호스트 데이터베이스 사용) - 권장

호스트 시스템의 MySQL/PostgreSQL 데이터베이스에 연결하여 MCP 서버만 Docker로 실행:

```bash
# MCP 서버만 빌드 및 실행 (host.docker.internal 사용)
docker-compose -f docker-compose.mcp-only.yml up --build

# 백그라운드에서 실행
docker-compose -f docker-compose.mcp-only.yml up --build -d
```

### 2. 전체 스택 실행

모든 서비스(데이터베이스 + MCP 서버)를 한 번에 실행:

```bash
# 모든 서비스 빌드 및 실행
docker-compose up --build

# 백그라운드에서 실행
docker-compose up --build -d
```

### 3. 개별 서비스 실행

#### MySQL MCP 서버만 실행
```bash
# MySQL MCP 서버 빌드
docker build -t mysql-mcp ./mysql-mcp

# MySQL MCP 서버 실행 (외부 MySQL 서버 연결 필요)
docker run -p 8012:8012 \
  -e MYSQL_CONNECTION_STRING=mysql://user:password@host:port/database \
  mysql-mcp
```

#### PostgreSQL MCP 서버만 실행
```bash
# PostgreSQL MCP 서버 빌드
docker build -t postgres-mcp ./postgres-mcp

# PostgreSQL MCP 서버 실행 (외부 PostgreSQL 서버 연결 필요)
docker run -p 8011:8011 \
  -e POSTGRES_CONNECTION_STRING=postgresql://user:password@host:port/database \
  postgres-mcp
```

## 🔧 서비스 정보

### 포트 매핑
- **MySQL 데이터베이스**: `localhost:3306` (호스트) 또는 `mysql:3306` (컨테이너)
- **PostgreSQL 데이터베이스**: `localhost:5432` (호스트) 또는 `postgres:5432` (컨테이너)
- **MySQL MCP 서버**: `localhost:8012`
- **PostgreSQL MCP 서버**: `localhost:8011`

### 기본 데이터베이스 설정
- **MySQL**: 사용자 `test`, 비밀번호 `test`, 데이터베이스 `test`
- **PostgreSQL**: 사용자 `test`, 비밀번호 `test`, 데이터베이스 `test`

### host.docker.internal 사용법
Docker 컨테이너에서 호스트 시스템의 서비스에 접근하려면 `host.docker.internal`을 사용합니다:

- **MCP 서버만 실행**: `docker-compose.mcp-only.yml` 사용
- **호스트 데이터베이스 연결**: `host.docker.internal:3306` (MySQL), `host.docker.internal:5432` (PostgreSQL)
- **extra_hosts 설정**: Docker Compose에서 `host.docker.internal:host-gateway` 매핑 필요

## 🛠️ 관리 명령어

### 서비스 상태 확인
```bash
# 실행 중인 컨테이너 확인
docker-compose ps

# 로그 확인
docker-compose logs

# 특정 서비스 로그 확인
docker-compose logs mysql-mcp
docker-compose logs postgres-mcp
```

### 서비스 중지 및 정리
```bash
# 서비스 중지
docker-compose down

# 서비스 중지 및 볼륨 삭제 (데이터 삭제됨)
docker-compose down -v

# 이미지까지 삭제
docker-compose down --rmi all -v
```

### 서비스 재시작
```bash
# 특정 서비스만 재시작
docker-compose restart mysql-mcp
docker-compose restart postgres-mcp

# 모든 서비스 재시작
docker-compose restart
```

## 🔍 문제 해결

### 1. 포트 충돌
이미 사용 중인 포트가 있다면 `docker-compose.yml`에서 포트를 변경하세요:
```yaml
ports:
  - "8013:8012"  # MySQL MCP 서버 포트 변경
  - "8014:8011"  # PostgreSQL MCP 서버 포트 변경
```

### 2. 데이터베이스 연결 오류
- 데이터베이스가 완전히 시작될 때까지 기다리세요 (healthcheck 완료)
- 연결 문자열이 올바른지 확인하세요
- 방화벽 설정을 확인하세요

### 3. 컨테이너 재빌드
코드 변경 후 컨테이너를 재빌드하려면:
```bash
docker-compose up --build
```

## 📊 MCP 서버 테스트

서버가 정상적으로 실행되면 다음 URL에서 접근할 수 있습니다:

- **MySQL MCP 서버**: http://localhost:8012
- **PostgreSQL MCP 서버**: http://localhost:8011

### 사용 가능한 도구들
- `list_databases()`: 데이터베이스 목록 조회
- `use_database(database_name)`: 데이터베이스 전환
- `query(sql, database)`: SQL 쿼리 실행
- `list_tables(database)`: 테이블 목록 조회
- `describe_table(table_name, database)`: 테이블 구조 조회
- `get_current_database()`: 현재 데이터베이스 확인

## 🔐 보안 고려사항

프로덕션 환경에서는 다음 사항을 고려하세요:

1. **강력한 비밀번호 사용**
2. **환경 변수로 민감한 정보 관리**
3. **네트워크 보안 설정**
4. **정기적인 보안 업데이트**

## 📝 환경 변수 커스터마이징

### MCP 서버만 실행하는 경우
`env.example` 파일을 참고하여 환경 변수를 설정하세요:

```bash
# env.example 파일을 .env로 복사
cp env.example .env

# .env 파일 편집
nano .env
```

`.env` 파일 예시:
```env
# MySQL 데이터베이스 연결 설정
MYSQL_CONNECTION_STRING=mysql://your_user:your_password@host.docker.internal:3306/your_database

# PostgreSQL 데이터베이스 연결 설정
POSTGRES_CONNECTION_STRING=postgresql://your_user:your_password@host.docker.internal:5432/your_database
```

### 전체 스택 실행하는 경우
`.env` 파일을 생성하여 환경 변수를 커스터마이징할 수 있습니다:

```env
# MySQL 설정
MYSQL_ROOT_PASSWORD=your_secure_password
MYSQL_DATABASE=your_database
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password

# PostgreSQL 설정
POSTGRES_DB=your_database
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
```

그리고 `docker-compose.yml`에서 환경 변수를 참조하도록 수정하세요.
