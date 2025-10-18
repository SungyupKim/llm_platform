# 🤖 LLM Agent & RAG System

**통합 AI 플랫폼**: 도구를 활용한 지능형 AI Agent와 PDF 문서 기반 RAG(Retrieval-Augmented Generation) 시스템을 하나의 플랫폼에서 제공합니다.

## ✨ 주요 기능

### 🧠 AI Agent
- **다중 도구 지원**: PostgreSQL, MySQL, 파일시스템, 웹검색, 계산기
- **실시간 스트리밍**: 답변을 실시간으로 스트리밍하여 표시
- **MCP 프로토콜**: Model Context Protocol을 통한 확장 가능한 도구 시스템
- **대화형 인터페이스**: 직관적인 웹 기반 채팅 인터페이스

### 📚 RAG System
- **PDF 문서 처리**: 한글 최적화된 PDF 파서로 문서 추출
- **지능형 검색**: Amazon Titan v2 임베딩을 활용한 의미 기반 검색
- **AI 기반 답변**: 검색된 문서를 참조하여 Claude 3.5 Sonnet이 답변 생성
- **실시간 스트리밍**: RAG 답변도 실시간으로 스트리밍 표시
- **벡터 데이터베이스**: ChromaDB를 활용한 효율적인 문서 저장 및 검색

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd llm_agent

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# AWS 설정
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-northeast-2

# 데이터베이스 연결 (선택사항)
POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/database
MYSQL_CONNECTION_STRING=mysql://user:password@localhost:3306/database

# 시스템 설정
MAX_ITERATIONS=15
```

### 3. 서버 실행

```bash
# 통합 서버 실행
python fastapi_app.py
```

서버가 실행되면 `http://localhost:8001`에서 접속할 수 있습니다.

## 🎯 사용 방법

### 메인 대시보드
`http://localhost:8001`에 접속하면 통합 대시보드가 표시됩니다:

- **💬 AI Agent**: 도구를 활용한 지능형 대화
- **📚 RAG System**: PDF 문서 기반 질의응답

### AI Agent 사용법

1. **AI Agent** 메뉴 클릭
2. 자연어로 질문 입력
3. AI가 필요한 도구를 자동으로 선택하여 작업 수행
4. 실시간으로 결과 확인

**지원 도구:**
- 📊 **데이터베이스**: PostgreSQL, MySQL 쿼리 실행
- 📁 **파일시스템**: 파일 읽기/쓰기, 디렉토리 탐색
- 🔍 **웹검색**: 실시간 정보 검색
- 🧮 **계산기**: 수학 연산 수행

### RAG System 사용법

1. **RAG System** 메뉴 클릭
2. **PDF 업로드**: 분석할 PDF 파일 업로드
3. **문서 검색**: 관련 내용 검색
4. **AI 채팅**: 업로드된 문서에 대해 질문

**특징:**
- 📄 한글 PDF 최적화 파싱
- 🔍 의미 기반 문서 검색
- 💬 문서 참조 AI 답변
- ⚡ 실시간 스트리밍 응답

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    통합 웹 인터페이스                        │
│                    (FastAPI + Jinja2)                      │
└─────────────────────┬───────────────────┬───────────────────┘
                      │                   │
            ┌─────────▼─────────┐ ┌───────▼────────┐
            │    AI Agent       │ │  RAG System    │
            │                   │ │                │
            │ • MCP Client      │ │ • PDF Parser   │
            │ • Tool Manager    │ │ • Embeddings   │
            │ • Streaming       │ │ • Vector DB    │
            │ • Claude 3.5      │ │ • Streaming    │
            └─────────┬─────────┘ └───────┬────────┘
                      │                   │
            ┌─────────▼─────────┐ ┌───────▼────────┐
            │   MCP Servers     │ │   ChromaDB     │
            │                   │ │                │
            │ • PostgreSQL      │ │ • Vector Store │
            │ • MySQL           │ │ • Metadata     │
            │ • Filesystem      │ │ • Search       │
            │ • Web Search      │ │                │
            │ • Calculator      │ │                │
            └───────────────────┘ └────────────────┘
```

## 🔧 기술 스택

### Backend
- **FastAPI**: 고성능 웹 프레임워크
- **LangChain**: LLM 애플리케이션 프레임워크
- **AWS Bedrock**: Claude 3.5 Sonnet, Titan v2 임베딩
- **ChromaDB**: 벡터 데이터베이스
- **PyMuPDF + pdfplumber**: PDF 파싱

### Frontend
- **HTML5 + CSS3**: 반응형 웹 인터페이스
- **JavaScript**: 실시간 스트리밍 처리
- **Server-Sent Events**: 실시간 데이터 스트리밍

### Database
- **PostgreSQL**: 관계형 데이터베이스
- **MySQL**: 관계형 데이터베이스
- **ChromaDB**: 벡터 데이터베이스

## 📁 프로젝트 구조

```
llm_agent/
├── fastapi_app.py          # 메인 FastAPI 애플리케이션
├── streaming_agent.py      # AI Agent 핵심 로직
├── rag_system.py          # RAG 시스템 핵심 로직
├── mcp_client.py          # MCP 클라이언트
├── bedrock_client.py      # AWS Bedrock 클라이언트
├── config.py              # 설정 관리
├── templates/             # HTML 템플릿
│   ├── main.html         # 메인 대시보드
│   └── rag.html          # RAG 인터페이스
├── static/               # 정적 파일
├── multi_db_postgres_mcp.py  # PostgreSQL MCP 서버
├── multi_db_mysql_mcp.py     # MySQL MCP 서버
├── calculator_mcp.py         # 계산기 MCP 서버
├── requirements.txt          # Python 의존성
├── .env                     # 환경 변수
└── README.md               # 프로젝트 문서
```

## 🔌 MCP 서버

Model Context Protocol을 통해 확장 가능한 도구 시스템을 제공합니다:

### PostgreSQL MCP 서버
- 데이터베이스 목록 조회
- 테이블 구조 분석
- SQL 쿼리 실행
- 스키마 정보 조회

### MySQL MCP 서버
- 데이터베이스 목록 조회
- 테이블 구조 분석
- SQL 쿼리 실행
- 스키마 정보 조회

### 파일시스템 MCP 서버
- 파일 읽기/쓰기
- 디렉토리 탐색
- 파일 검색
- 메타데이터 조회

### 웹검색 MCP 서버
- 실시간 웹 검색
- 검색 결과 요약
- 관련 정보 추출

## 🎨 UI/UX 특징

### 반응형 디자인
- 모바일과 데스크톱 모두 지원
- 직관적인 네비게이션
- 실시간 상태 표시

### 스트리밍 인터페이스
- AI 답변 실시간 표시
- 진행 상황 시각화
- 에러 처리 및 피드백

### 통합 대시보드
- AI Agent와 RAG System 간 원클릭 전환
- 시스템 상태 모니터링
- 일관된 사용자 경험

## 🚀 고급 기능

### RAG 시스템
- **다중 PDF 지원**: 여러 문서를 동시에 처리
- **청킹 전략**: 의미 단위로 문서 분할
- **메타데이터 관리**: 파일명, 페이지, 청크 정보 추적
- **유사도 검색**: 정확한 관련 문서 검색

### AI Agent
- **도구 자동 선택**: 상황에 맞는 도구 자동 선택
- **반복 실행**: 복잡한 작업의 단계별 실행
- **에러 복구**: 실패한 작업의 자동 재시도
- **컨텍스트 유지**: 대화 히스토리 기반 연속 작업

## 🔒 보안 및 설정

### 환경 변수 관리
- `.env` 파일을 통한 안전한 설정 관리
- AWS 자격 증명 보안
- 데이터베이스 연결 정보 암호화

### 접근 제어
- 로컬 네트워크 접근 제한
- CORS 설정
- 요청 제한 및 검증

## 📊 성능 최적화

### 벡터 검색
- ChromaDB 인덱싱
- 임베딩 캐싱
- 배치 처리

### 스트리밍
- 청크 단위 응답
- 버퍼링 최적화
- 연결 풀 관리

## 🛠️ 개발 및 배포

### 개발 환경
```bash
# 개발 서버 실행 (자동 리로드)
python fastapi_app.py

# 개별 MCP 서버 테스트
python multi_db_postgres_mcp.py
python multi_db_mysql_mcp.py
```

### 프로덕션 배포
```bash
# Gunicorn으로 배포
gunicorn fastapi_app:app -w 4 -k uvicorn.workers.UvicornWorker

# Docker 컨테이너화
docker build -t llm-agent .
docker run -p 8001:8001 llm-agent
```

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🆘 문제 해결

### 일반적인 문제

**Q: AWS Bedrock 접근 오류가 발생합니다.**
A: AWS 자격 증명과 Bedrock 서비스 접근 권한을 확인하세요.

**Q: PDF 파싱이 실패합니다.**
A: PDF 파일이 손상되지 않았는지 확인하고, 한글 폰트가 포함된 PDF를 사용해보세요.

**Q: 데이터베이스 연결이 안 됩니다.**
A: 데이터베이스 서버가 실행 중인지 확인하고, 연결 문자열을 검증하세요.

### 로그 확인
```bash
# 서버 로그 확인
tail -f app.log

# 디버그 모드 실행
DEBUG=1 python fastapi_app.py
```

## 📞 지원

문제가 발생하거나 기능 요청이 있으시면 GitHub Issues를 통해 문의해주세요.

---

**🎉 LLM Agent & RAG System으로 더 스마트한 AI 경험을 시작하세요!**