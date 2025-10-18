#!/usr/bin/env python3
"""
RAG 시스템 웹 UI
FastAPI 기반 PDF 업로드 및 검색 인터페이스
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import shutil
from datetime import datetime

# FastAPI 및 웹 관련
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# RAG 시스템
from rag_system import rag_system

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="RAG System",
    description="PDF 기반 RAG (Retrieval-Augmented Generation) 시스템",
    version="1.0.0"
)

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 업로드 디렉토리 생성
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = Form(""),
    description: str = Form(""),
    tags: str = Form("")
):
    """
    PDF 파일 업로드 및 처리
    
    Args:
        file: 업로드된 PDF 파일
        title: 문서 제목
        description: 문서 설명
        tags: 문서 태그 (쉼표로 구분)
    
    Returns:
        처리 결과
    """
    try:
        # 파일 확장자 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")
        
        # 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        file_path = UPLOAD_DIR / filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"파일 업로드 완료: {filename}")
        
        # 메타데이터 준비
        metadata = {
            "title": title or file.filename,
            "description": description,
            "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
            "uploaded_at": datetime.now().isoformat(),
            "file_size": file_path.stat().st_size
        }
        
        # RAG 시스템에서 처리
        success = await rag_system.process_pdf(str(file_path), metadata)
        
        if success:
            return JSONResponse({
                "success": True,
                "message": "PDF 파일이 성공적으로 처리되었습니다",
                "filename": filename,
                "metadata": metadata
            })
        else:
            # 실패 시 파일 삭제
            file_path.unlink()
            raise HTTPException(status_code=500, detail="PDF 처리에 실패했습니다")
    
    except Exception as e:
        logger.error(f"파일 업로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"업로드 오류: {str(e)}")

@app.post("/search")
async def search_documents(
    query: str = Form(...),
    n_results: int = Form(5)
):
    """
    문서 검색
    
    Args:
        query: 검색 쿼리
        n_results: 반환할 결과 수
    
    Returns:
        검색 결과
    """
    try:
        if not query.strip():
            raise HTTPException(status_code=400, detail="검색 쿼리를 입력해주세요")
        
        # RAG 검색 수행
        results = await rag_system.search(query, n_results)
        
        return JSONResponse({
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results)
        })
    
    except Exception as e:
        logger.error(f"검색 오류: {e}")
        raise HTTPException(status_code=500, detail=f"검색 오류: {str(e)}")

@app.get("/collection/info")
async def get_collection_info():
    """컬렉션 정보 조회"""
    try:
        info = rag_system.get_collection_info()
        return JSONResponse({
            "success": True,
            "info": info
        })
    except Exception as e:
        logger.error(f"컬렉션 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"정보 조회 오류: {str(e)}")

@app.delete("/collection/clear")
async def clear_collection():
    """컬렉션 초기화"""
    try:
        # 기존 컬렉션 삭제
        try:
            rag_system.chroma_client.delete_collection(rag_system.collection_name)
        except:
            pass
        
        # 새 컬렉션 생성
        rag_system.collection = rag_system.chroma_client.create_collection(
            name=rag_system.collection_name,
            metadata={"description": "RAG 문서 컬렉션"}
        )
        
        return JSONResponse({
            "success": True,
            "message": "컬렉션이 초기화되었습니다"
        })
    
    except Exception as e:
        logger.error(f"컬렉션 초기화 오류: {e}")
        raise HTTPException(status_code=500, detail=f"초기화 오류: {str(e)}")

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "RAG System"
    })

# HTML 템플릿 생성
def create_templates():
    """HTML 템플릿 파일 생성"""
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)
    
    # index.html 템플릿
    index_html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG System - PDF 기반 검색</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .content {
            padding: 40px;
        }
        
        .section {
            margin-bottom: 40px;
            padding: 30px;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            background: #fafafa;
        }
        
        .section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        
        input[type="file"], input[type="text"], input[type="number"], textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input[type="file"]:focus, input[type="text"]:focus, input[type="number"]:focus, textarea:focus {
            outline: none;
            border-color: #4facfe;
        }
        
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        
        .btn {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(79, 172, 254, 0.3);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .search-results {
            margin-top: 20px;
        }
        
        .result-item {
            background: white;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border-left: 4px solid #4facfe;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .result-text {
            margin-bottom: 10px;
            line-height: 1.6;
        }
        
        .result-metadata {
            font-size: 0.9em;
            color: #666;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        
        .success {
            background: #e8f5e8;
            color: #2e7d32;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        
        .info-panel {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .info-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        
        .info-label {
            font-weight: 600;
            color: #1976d2;
        }
        
        .info-value {
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 RAG System</h1>
            <p>PDF 기반 지능형 검색 시스템</p>
        </div>
        
        <div class="content">
            <!-- 컬렉션 정보 -->
            <div class="info-panel">
                <h3>📊 시스템 정보</h3>
                <div id="collection-info">
                    <div class="loading">정보를 불러오는 중...</div>
                </div>
            </div>
            
            <!-- PDF 업로드 섹션 -->
            <div class="section">
                <h2>📄 PDF 문서 업로드</h2>
                <form id="upload-form" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="file">PDF 파일 선택:</label>
                        <input type="file" id="file" name="file" accept=".pdf" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="title">문서 제목 (선택사항):</label>
                        <input type="text" id="title" name="title" placeholder="문서 제목을 입력하세요">
                    </div>
                    
                    <div class="form-group">
                        <label for="description">문서 설명 (선택사항):</label>
                        <textarea id="description" name="description" placeholder="문서에 대한 설명을 입력하세요"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="tags">태그 (선택사항):</label>
                        <input type="text" id="tags" name="tags" placeholder="태그를 쉼표로 구분하여 입력하세요">
                    </div>
                    
                    <button type="submit" class="btn">📤 문서 업로드 및 처리</button>
                </form>
                
                <div id="upload-result"></div>
            </div>
            
            <!-- 검색 섹션 -->
            <div class="section">
                <h2>🔍 문서 검색</h2>
                <form id="search-form">
                    <div class="form-group">
                        <label for="query">검색 쿼리:</label>
                        <input type="text" id="query" name="query" placeholder="검색하고 싶은 내용을 입력하세요" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="n_results">결과 개수:</label>
                        <input type="number" id="n_results" name="n_results" value="5" min="1" max="20">
                    </div>
                    
                    <button type="submit" class="btn">🔍 검색</button>
                </form>
                
                <div id="search-results"></div>
            </div>
            
            <!-- 관리 섹션 -->
            <div class="section">
                <h2>⚙️ 시스템 관리</h2>
                <button onclick="clearCollection()" class="btn" style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);">
                    🗑️ 컬렉션 초기화
                </button>
            </div>
        </div>
    </div>
    
    <script>
        // 페이지 로드 시 컬렉션 정보 조회
        document.addEventListener('DOMContentLoaded', function() {
            loadCollectionInfo();
        });
        
        // 컬렉션 정보 로드
        async function loadCollectionInfo() {
            try {
                const response = await fetch('/collection/info');
                const data = await response.json();
                
                if (data.success) {
                    const info = data.info;
                    document.getElementById('collection-info').innerHTML = `
                        <div class="info-item">
                            <span class="info-label">컬렉션 이름:</span>
                            <span class="info-value">${info.collection_name || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">총 문서 수:</span>
                            <span class="info-value">${info.total_documents || 0}개</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">청크 크기:</span>
                            <span class="info-value">${info.chunk_size || 'N/A'}자</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">청크 겹침:</span>
                            <span class="info-value">${info.chunk_overlap || 'N/A'}자</span>
                        </div>
                    `;
                } else {
                    document.getElementById('collection-info').innerHTML = 
                        '<div class="error">컬렉션 정보를 불러올 수 없습니다.</div>';
                }
            } catch (error) {
                document.getElementById('collection-info').innerHTML = 
                    '<div class="error">컬렉션 정보 조회 중 오류가 발생했습니다.</div>';
            }
        }
        
        // 파일 업로드 처리
        document.getElementById('upload-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            const fileInput = document.getElementById('file');
            const title = document.getElementById('title').value;
            const description = document.getElementById('description').value;
            const tags = document.getElementById('tags').value;
            
            if (!fileInput.files[0]) {
                showUploadResult('파일을 선택해주세요.', 'error');
                return;
            }
            
            formData.append('file', fileInput.files[0]);
            formData.append('title', title);
            formData.append('description', description);
            formData.append('tags', tags);
            
            const submitBtn = e.target.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = '처리 중...';
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showUploadResult(`✅ ${data.message}`, 'success');
                    document.getElementById('upload-form').reset();
                    loadCollectionInfo(); // 정보 새로고침
                } else {
                    showUploadResult(`❌ ${data.message}`, 'error');
                }
            } catch (error) {
                showUploadResult(`❌ 업로드 오류: ${error.message}`, 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '📤 문서 업로드 및 처리';
            }
        });
        
        // 검색 처리
        document.getElementById('search-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            const query = document.getElementById('query').value;
            const nResults = document.getElementById('n_results').value;
            
            formData.append('query', query);
            formData.append('n_results', nResults);
            
            const submitBtn = e.target.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = '검색 중...';
            
            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSearchResults(data.results, data.query);
                } else {
                    showSearchResults([], data.query, `❌ ${data.message}`);
                }
            } catch (error) {
                showSearchResults([], query, `❌ 검색 오류: ${error.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '🔍 검색';
            }
        });
        
        // 업로드 결과 표시
        function showUploadResult(message, type) {
            const resultDiv = document.getElementById('upload-result');
            resultDiv.innerHTML = `<div class="${type}">${message}</div>`;
        }
        
        // 검색 결과 표시
        function showSearchResults(results, query, errorMessage = null) {
            const resultsDiv = document.getElementById('search-results');
            
            if (errorMessage) {
                resultsDiv.innerHTML = `<div class="error">${errorMessage}</div>`;
                return;
            }
            
            if (results.length === 0) {
                resultsDiv.innerHTML = `<div class="error">'${query}'에 대한 검색 결과가 없습니다.</div>`;
                return;
            }
            
            let html = `<h3>🔍 '${query}' 검색 결과 (${results.length}개)</h3>`;
            
            results.forEach((result, index) => {
                const metadata = result.metadata || {};
                const distance = result.distance ? (1 - result.distance).toFixed(3) : 'N/A';
                
                html += `
                    <div class="result-item">
                        <div class="result-text">
                            <strong>결과 ${index + 1}</strong> (유사도: ${distance})
                            <br><br>
                            ${result.text}
                        </div>
                        <div class="result-metadata">
                            <strong>출처:</strong> ${metadata.source_file || 'Unknown'} |
                            <strong>청크:</strong> ${metadata.chunk_index || 'N/A'} |
                            <strong>크기:</strong> ${metadata.chunk_size || 'N/A'}자
                            ${metadata.title ? ` | <strong>제목:</strong> ${metadata.title}` : ''}
                        </div>
                    </div>
                `;
            });
            
            resultsDiv.innerHTML = html;
        }
        
        // 컬렉션 초기화
        async function clearCollection() {
            if (!confirm('정말로 모든 문서를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
                return;
            }
            
            try {
                const response = await fetch('/collection/clear', {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('✅ 컬렉션이 초기화되었습니다.');
                    loadCollectionInfo();
                    document.getElementById('search-results').innerHTML = '';
                } else {
                    alert(`❌ 초기화 실패: ${data.message}`);
                }
            } catch (error) {
                alert(`❌ 초기화 오류: ${error.message}`);
            }
        }
    </script>
</body>
</html>
    """
    
    with open(templates_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    logger.info("HTML 템플릿 생성 완료")

if __name__ == "__main__":
    # 템플릿 생성
    create_templates()
    
    # 서버 실행
    logger.info("RAG 웹 UI 서버 시작...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
