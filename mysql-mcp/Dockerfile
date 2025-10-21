# MySQL MCP Server Dockerfile
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY fastmcp_mysql_server.py .

# 포트 노출 (MySQL MCP 서버는 8012 포트 사용)
EXPOSE 8012

# 환경 변수 설정 (기본값)
ENV MYSQL_CONNECTION_STRING=mysql://test:test@host.docker.internal:3306/test

# 애플리케이션 실행
CMD ["python", "fastmcp_mysql_server.py"]
