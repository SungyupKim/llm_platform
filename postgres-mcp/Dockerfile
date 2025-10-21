# PostgreSQL MCP Server Dockerfile
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY fastmcp_postgres_server.py .

# 포트 노출 (PostgreSQL MCP 서버는 8011 포트 사용)
EXPOSE 8011

# 환경 변수 설정 (기본값)
ENV POSTGRES_CONNECTION_STRING=postgresql://test:test@host.docker.internal:5432/test

# 애플리케이션 실행
CMD ["python", "fastmcp_postgres_server.py"]
