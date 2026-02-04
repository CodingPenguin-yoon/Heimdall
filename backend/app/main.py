"""
FastAPI 메인 애플리케이션 진입점

이 모듈은 Terraform과 Ansible을 제어하는 백엔드 서버의 핵심 엔트리포인트입니다.
- CORS 설정을 통해 프론트엔드(포트 5173)와 통신
- API 라우트를 등록하여 인프라 배포 및 상태 관리 기능 제공
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import deploy, status, logs, proxmox, llm

# 환경 변수 로드 (.env 파일에서)
# proxmox_service.py에서도 로드하지만, 다른 서비스들을 위해 여기서도 로드
project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(
    title="Terraform & Ansible Control API",
    description="인프라 배포를 위한 Terraform 및 Ansible 제어 백엔드",
    version="1.0.0"
)

# CORS 설정: 프론트엔드로부터의 요청 허용
frontend_port = os.getenv("FRONTEND_PORT", "5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우트 등록
app.include_router(deploy.router, prefix="/api", tags=["deploy"])
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(proxmox.router, prefix="/api", tags=["proxmox"])
app.include_router(llm.router, prefix="/api", tags=["llm"])


@app.get("/")
async def root():
    """헬스체크 엔드포인트"""
    return {"message": "Terraform & Ansible Control API", "status": "running"}


@app.get("/health")
async def health():
    """상세 헬스체크 엔드포인트"""
    return {"status": "healthy", "service": "backend"}
