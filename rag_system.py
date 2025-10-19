#!/usr/bin/env python3
"""
RAG (Retrieval-Augmented Generation) System
PDF 파싱, 청킹, 임베딩, 벡터 검색을 통한 RAG 시스템
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
from datetime import datetime

# PDF 파싱
import fitz  # PyMuPDF
import pdfplumber

# 텍스트 처리
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 벡터 DB
import chromadb
from chromadb.config import Settings

# AWS Bedrock
import boto3
from langchain_aws import BedrockEmbeddings, ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 환경변수 로딩
from dotenv import load_dotenv
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGSystem:
    """RAG 시스템 메인 클래스"""
    
    def __init__(self, 
                 collection_name: str = "rag_documents",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        """
        RAG 시스템 초기화
        
        Args:
            collection_name: ChromaDB 컬렉션 이름
            chunk_size: 청크 크기
            chunk_overlap: 청크 겹침 크기
        """
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # AWS Bedrock 클라이언트 초기화
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
        )
        
        # 임베딩 모델 초기화
        self.embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v2:0",
            client=self.bedrock_client
        )
        
        # LLM 모델 초기화 (기존 agent와 동일한 설정)
        self.llm = ChatBedrock(
            client=self.bedrock_client,
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            model_kwargs={
                "temperature": 0.1,
                "max_tokens": 2000
            }
        )
        
        # ChromaDB 초기화
        self.chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 컬렉션 가져오기 또는 생성
        try:
            self.collection = self.chroma_client.get_collection(
                name=self.collection_name
            )
            logger.info(f"기존 컬렉션 '{self.collection_name}' 로드됨")
        except:
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "RAG 문서 컬렉션"}
            )
            logger.info(f"새 컬렉션 '{self.collection_name}' 생성됨")
        
        # 텍스트 분할기 초기화
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        )
    
    def parse_pdf_pymupdf(self, pdf_path: str) -> str:
        """
        PyMuPDF를 사용한 PDF 파싱 (한글 지원 우수)
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            파싱된 텍스트
        """
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                text += f"\n--- 페이지 {page_num + 1} ---\n"
                text += page_text
                text += "\n"
            
            doc.close()
            logger.info(f"PyMuPDF로 PDF 파싱 완료: {len(text)} 문자")
            return text
            
        except Exception as e:
            logger.error(f"PyMuPDF 파싱 오류: {e}")
            return ""
    
    def parse_pdf_pdfplumber(self, pdf_path: str) -> str:
        """
        pdfplumber를 사용한 PDF 파싱 (표, 레이아웃 지원 우수)
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            파싱된 텍스트
        """
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- 페이지 {page_num + 1} ---\n"
                        text += page_text
                        text += "\n"
            
            logger.info(f"pdfplumber로 PDF 파싱 완료: {len(text)} 문자")
            return text
            
        except Exception as e:
            logger.error(f"pdfplumber 파싱 오류: {e}")
            return ""
    
    def parse_pdf(self, pdf_path: str, method: str = "pymupdf") -> str:
        """
        PDF 파싱 (여러 방법 시도)
        
        Args:
            pdf_path: PDF 파일 경로
            method: 파싱 방법 ("pymupdf" 또는 "pdfplumber")
            
        Returns:
            파싱된 텍스트
        """
        if method == "pymupdf":
            text = self.parse_pdf_pymupdf(pdf_path)
        elif method == "pdfplumber":
            text = self.parse_pdf_pdfplumber(pdf_path)
        else:
            # 두 방법 모두 시도
            text = self.parse_pdf_pymupdf(pdf_path)
            if not text or len(text.strip()) < 100:
                logger.info("PyMuPDF 결과가 부족하여 pdfplumber 시도")
                text = self.parse_pdf_pdfplumber(pdf_path)
        
        return text
    
    def clean_text(self, text: str) -> str:
        """
        텍스트 정리 (한글 특화)
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정리된 텍스트
        """
        # 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        # 특수 문자 정리
        text = re.sub(r'[^\w\s가-힣.,!?;:()\[\]{}"\'-]', '', text)
        
        # 연속된 줄바꿈 제거
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        텍스트를 청크로 분할
        
        Args:
            text: 분할할 텍스트
            
        Returns:
            청크 리스트
        """
        # 텍스트 정리
        cleaned_text = self.clean_text(text)
        
        # 청크 분할
        chunks = self.text_splitter.split_text(cleaned_text)
        
        # 청크 메타데이터 추가
        chunk_docs = []
        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) > 50:  # 너무 짧은 청크 제외
                chunk_docs.append({
                    "id": str(uuid.uuid4()),
                    "text": chunk.strip(),
                    "chunk_index": i,
                    "chunk_size": len(chunk),
                    "created_at": datetime.now().isoformat()
                })
        
        logger.info(f"텍스트를 {len(chunk_docs)}개 청크로 분할")
        return chunk_docs
    
    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        청크들을 임베딩으로 변환
        
        Args:
            chunks: 청크 리스트
            
        Returns:
            임베딩이 추가된 청크 리스트
        """
        try:
            # 텍스트만 추출
            texts = [chunk["text"] for chunk in chunks]
            
            # 임베딩 생성
            embeddings = self.embeddings.embed_documents(texts)
            
            # 임베딩을 청크에 추가
            for i, chunk in enumerate(chunks):
                chunk["embedding"] = embeddings[i]
            
            logger.info(f"{len(chunks)}개 청크 임베딩 완료")
            return chunks
            
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {e}")
            return chunks
    
    def store_chunks(self, chunks: List[Dict[str, Any]], 
                    document_metadata: Dict[str, Any] = None) -> bool:
        """
        청크들을 ChromaDB에 저장
        
        Args:
            chunks: 임베딩된 청크 리스트
            document_metadata: 문서 메타데이터
            
        Returns:
            저장 성공 여부
        """
        try:
            if not chunks:
                logger.warning("저장할 청크가 없습니다")
                return False
            
            # 메타데이터 준비
            if document_metadata is None:
                document_metadata = {}
            
            # ChromaDB에 저장
            ids = [chunk["id"] for chunk in chunks]
            texts = [chunk["text"] for chunk in chunks]
            embeddings = [chunk["embedding"] for chunk in chunks]
            
            metadatas = []
            for chunk in chunks:
                metadata = {
                    "chunk_index": chunk["chunk_index"],
                    "chunk_size": chunk["chunk_size"],
                    "created_at": chunk["created_at"],
                    **document_metadata
                }
                
                # ChromaDB는 리스트 타입을 지원하지 않으므로 문자열로 변환
                for key, value in metadata.items():
                    if isinstance(value, list):
                        metadata[key] = ", ".join(str(v) for v in value)
                    elif not isinstance(value, (str, int, float, bool, type(None))):
                        metadata[key] = str(value)
                
                metadatas.append(metadata)
            
            self.collection.add(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            logger.info(f"{len(chunks)}개 청크를 ChromaDB에 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"ChromaDB 저장 오류: {e}")
            return False
    
    async def process_pdf(self, pdf_path: str, 
                         document_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        PDF 파일을 처리하여 RAG 시스템에 추가
        
        Args:
            pdf_path: PDF 파일 경로
            document_metadata: 문서 메타데이터
            
        Returns:
            처리 결과 딕셔너리
        """
        try:
            logger.info(f"PDF 처리 시작: {pdf_path}")
            
            # PDF 파싱
            text = self.parse_pdf(pdf_path)
            if not text or len(text.strip()) < 100:
                logger.error("PDF 파싱 결과가 부족합니다")
                return {
                    "success": False,
                    "error": "PDF 파싱 결과가 부족합니다",
                    "chunks_created": 0,
                    "total_chunks": 0
                }
            
            # 텍스트 청킹
            chunks = self.chunk_text(text)
            if not chunks:
                logger.error("청크 생성에 실패했습니다")
                return {
                    "success": False,
                    "error": "청크 생성에 실패했습니다",
                    "chunks_created": 0,
                    "total_chunks": 0
                }
            
            # 임베딩 생성
            chunks_with_embeddings = self.embed_chunks(chunks)
            
            # 메타데이터 준비
            if document_metadata is None:
                document_metadata = {}
            
            document_metadata.update({
                "source_file": os.path.basename(pdf_path),
                "file_path": pdf_path,
                "total_chunks": len(chunks),
                "processed_at": datetime.now().isoformat()
            })
            
            # ChromaDB에 저장
            success = self.store_chunks(chunks_with_embeddings, document_metadata)
            
            if success:
                logger.info(f"PDF 처리 완료: {pdf_path}")
                return {
                    "success": True,
                    "chunks_created": len(chunks),
                    "total_chunks": len(chunks),
                    "message": f"PDF '{os.path.basename(pdf_path)}' 처리 완료"
                }
            else:
                logger.error(f"PDF 저장 실패: {pdf_path}")
                return {
                    "success": False,
                    "error": "PDF 저장 실패",
                    "chunks_created": 0,
                    "total_chunks": 0
                }
            
        except Exception as e:
            logger.error(f"PDF 처리 오류: {e}")
            return {
                "success": False,
                "error": f"PDF 처리 오류: {str(e)}",
                "chunks_created": 0,
                "total_chunks": 0
            }
    
    def process_pdf_bytes(self, pdf_bytes: bytes, filename: str,
                               document_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        PDF 바이트 데이터를 처리하여 RAG 시스템에 추가
        
        Args:
            pdf_bytes: PDF 파일의 바이트 데이터
            filename: 파일명
            document_metadata: 문서 메타데이터
            
        Returns:
            처리 결과 딕셔너리
        """
        import tempfile
        import os
        
        try:
            logger.info(f"PDF 바이트 처리 시작: {filename}")
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = temp_file.name
            
            try:
                # PDF 파싱
                text = self.parse_pdf(temp_path)
                if not text or len(text.strip()) < 100:
                    logger.error("PDF 파싱 결과가 부족합니다")
                    return {
                        "success": False,
                        "error": "PDF 파싱 결과가 부족합니다",
                        "chunks_created": 0,
                        "total_chunks": 0
                    }
                
                # 텍스트 청킹
                chunks = self.chunk_text(text)
                if not chunks:
                    logger.error("청크 생성에 실패했습니다")
                    return {
                        "success": False,
                        "error": "청크 생성에 실패했습니다",
                        "chunks_created": 0,
                        "total_chunks": 0
                    }
                
                # 임베딩 생성
                chunks_with_embeddings = self.embed_chunks(chunks)
                
                # 메타데이터 준비
                if document_metadata is None:
                    document_metadata = {}
                
                document_metadata.update({
                    "source_file": filename,
                    "filename": filename,
                    "total_chunks": len(chunks),
                    "processed_at": datetime.now().isoformat()
                })
                
                # ChromaDB에 저장
                success = self.store_chunks(chunks_with_embeddings, document_metadata)
                
                if success:
                    logger.info(f"PDF 바이트 처리 완료: {filename}")
                    return {
                        "success": True,
                        "chunks_created": len(chunks),
                        "total_chunks": len(chunks),
                        "message": f"PDF '{filename}' 처리 완료"
                    }
                else:
                    logger.error(f"PDF 저장 실패: {filename}")
                    return {
                        "success": False,
                        "error": "PDF 저장 실패",
                        "chunks_created": 0,
                        "total_chunks": 0
                    }
                    
            finally:
                # 임시 파일 삭제
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"PDF 바이트 처리 오류: {e}")
            return {
                "success": False,
                "error": f"PDF 처리 오류: {str(e)}",
                "chunks_created": 0,
                "total_chunks": 0
            }
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        RAG 검색 수행
        
        Args:
            query: 검색 쿼리
            n_results: 반환할 결과 수
            
        Returns:
            검색 결과 리스트
        """
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embeddings.embed_query(query)
            
            # ChromaDB에서 검색
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            # 결과 포맷팅
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    distance = results['distances'][0][i] if results['distances'] and results['distances'][0] else 0
                    metadata = results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {}
                    
                    # distance를 similarity score로 변환 (0-1 범위)
                    # ChromaDB의 distance는 작을수록 유사함 (0에 가까울수록 유사)
                    # similarity = 1 / (1 + distance) 또는 1 - distance (distance가 0-1 범위인 경우)
                    similarity = 1 / (1 + distance) if distance > 0 else 1.0
                    
                    formatted_results.append({
                        "text": results['documents'][0][i],
                        "metadata": metadata,
                        "distance": distance,
                        "score": similarity
                    })
            
            logger.info(f"검색 완료: '{query}' -> {len(formatted_results)}개 결과")
            return formatted_results
            
        except Exception as e:
            logger.error(f"검색 오류: {e}")
            return []
    
    def rag_chat(self, query: str, n_results: int = 3) -> Dict[str, Any]:
        """
        RAG 기반 채팅 - 검색된 문서를 참조하여 LLM이 답변 생성
        
        Args:
            query: 사용자 질문
            n_results: 검색할 문서 수
            
        Returns:
            답변과 참조 문서 정보
        """
        try:
            logger.info(f"RAG 채팅 시작: '{query}'")
            
            # 1. 관련 문서 검색
            search_results = self.search(query, n_results=n_results)
            
            if not search_results:
                return {
                    "answer": "죄송합니다. 관련된 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요.",
                    "sources": [],
                    "query": query
                }
            
            # 2. 검색된 문서들을 컨텍스트로 구성
            context_docs = []
            sources = []
            
            for i, result in enumerate(search_results):
                context_docs.append(f"[문서 {i+1}] {result['text']}")
                sources.append({
                    "text": result['text'][:200] + "..." if len(result['text']) > 200 else result['text'],
                    "filename": result['metadata'].get('filename', result['metadata'].get('source_file', 'Unknown')),
                    "score": result['score'],
                    "chunk_index": result['metadata'].get('chunk_index', 'N/A')
                })
            
            context = "\n\n".join(context_docs)
            
            # 3. 프롬프트 템플릿 생성
            prompt_template = ChatPromptTemplate.from_template("""
다음 문서들을 참조하여 사용자의 질문에 정확하고 도움이 되는 답변을 제공해주세요.

참조 문서:
{context}

사용자 질문: {question}

답변 가이드라인:
1. 참조 문서의 내용을 바탕으로 정확한 정보를 제공하세요.
2. 답변할 수 없는 내용은 "문서에서 해당 정보를 찾을 수 없습니다"라고 명시하세요.
3. 답변은 한국어로 작성하세요.
4. 답변의 근거가 되는 문서 번호를 [문서 X] 형태로 언급하세요.
5. 간결하고 명확하게 답변하세요.

답변:
""")
            
            # 4. RAG 체인 구성
            rag_chain = (
                {"context": RunnablePassthrough(), "question": RunnablePassthrough()}
                | prompt_template
                | self.llm
                | StrOutputParser()
            )
            
            # 5. LLM 답변 생성
            answer = rag_chain.invoke({
                "context": context,
                "question": query
            })
            
            logger.info(f"RAG 채팅 완료: '{query}' -> 답변 길이: {len(answer)}")
            
            return {
                "answer": answer,
                "sources": sources,
                "query": query,
                "total_sources": len(sources)
            }
            
        except Exception as e:
            logger.error(f"RAG 채팅 오류: {e}")
            return {
                "answer": f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
                "sources": [],
                "query": query,
                "error": str(e)
            }
    
    async def rag_chat_stream(self, query: str, n_results: int = 3):
        """
        RAG 기반 스트리밍 채팅 - 검색된 문서를 참조하여 LLM이 스트리밍으로 답변 생성
        
        Args:
            query: 사용자 질문
            n_results: 검색할 문서 수
            
        Yields:
            스트리밍 업데이트 딕셔너리
        """
        try:
            logger.info(f"RAG 스트리밍 채팅 시작: '{query}'")
            
            # 1. 관련 문서 검색
            yield {
                "type": "search_start",
                "message": "관련 문서를 검색하는 중..."
            }
            
            search_results = self.search(query, n_results=n_results)
            
            if not search_results:
                yield {
                    "type": "error",
                    "message": "죄송합니다. 관련된 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요."
                }
                return
            
            # 2. 검색된 문서들을 컨텍스트로 구성
            context_docs = []
            sources = []
            
            for i, result in enumerate(search_results):
                context_docs.append(f"[문서 {i+1}] {result['text']}")
                sources.append({
                    "text": result['text'][:200] + "..." if len(result['text']) > 200 else result['text'],
                    "filename": result['metadata'].get('filename', result['metadata'].get('source_file', 'Unknown')),
                    "score": result['score'],
                    "chunk_index": result['metadata'].get('chunk_index', 'N/A')
                })
            
            context = "\n\n".join(context_docs)
            
            yield {
                "type": "search_complete",
                "message": f"{len(search_results)}개 문서를 찾았습니다.",
                "sources": sources
            }
            
            # 3. 프롬프트 템플릿 생성
            prompt_template = ChatPromptTemplate.from_template("""
다음 문서들을 참조하여 사용자의 질문에 정확하고 도움이 되는 답변을 제공해주세요.

참조 문서:
{context}

사용자 질문: {question}

답변 가이드라인:
1. 참조 문서의 내용을 바탕으로 정확한 정보를 제공하세요.
2. 답변할 수 없는 내용은 "문서에서 해당 정보를 찾을 수 없습니다"라고 명시하세요.
3. 답변은 한국어로 작성하세요.
4. 답변의 근거가 되는 문서 번호를 [문서 X] 형태로 언급하세요.
5. 간결하고 명확하게 답변하세요.

답변:
""")
            
            # 4. RAG 체인 구성
            rag_chain = (
                {"context": RunnablePassthrough(), "question": RunnablePassthrough()}
                | prompt_template
                | self.llm
            )
            
            yield {
                "type": "generation_start",
                "message": "AI가 답변을 생성하는 중..."
            }
            
            # 5. LLM 스트리밍 답변 생성
            full_answer = ""
            async for chunk in rag_chain.astream({
                "context": context,
                "question": query
            }):
                if hasattr(chunk, 'content') and chunk.content:
                    full_answer += chunk.content
                    yield {
                        "type": "stream",
                        "chunk": chunk.content
                    }
            
            yield {
                "type": "response_complete",
                "message": full_answer,
                "sources": sources,
                "query": query,
                "total_sources": len(sources)
            }
            
            logger.info(f"RAG 스트리밍 채팅 완료: '{query}' -> 답변 길이: {len(full_answer)}")
            
        except Exception as e:
            logger.error(f"RAG 스트리밍 채팅 오류: {e}")
            yield {
                "type": "error",
                "message": f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}"
            }
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        컬렉션 정보 조회
        
        Returns:
            컬렉션 정보
        """
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_documents": count,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap
            }
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 오류: {e}")
            return {}

# 전역 RAG 시스템 인스턴스
rag_system = RAGSystem()

async def main():
    """테스트용 메인 함수"""
    # 테스트 PDF 파일이 있다면 처리
    test_pdf = "test.pdf"
    if os.path.exists(test_pdf):
        success = rag_system.process_pdf(test_pdf)
        if success:
            print("PDF 처리 성공!")
            
            # 검색 테스트
            results = rag_system.search("테스트 쿼리")
            print(f"검색 결과: {len(results)}개")
            for result in results:
                print(f"- {result['text'][:100]}...")
        else:
            print("PDF 처리 실패!")
    else:
        print("테스트 PDF 파일이 없습니다.")
    
    # 컬렉션 정보 출력
    info = rag_system.get_collection_info()
    print(f"컬렉션 정보: {info}")

if __name__ == "__main__":
    asyncio.run(main())
