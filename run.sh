#!/bin/bash

# Terraform & Ansible 통합 배포 플랫폼 실행 스크립트
# 이 스크립트는 백엔드와 프론트엔드를 동시에 실행합니다.

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 프로젝트 루트 디렉토리 확인
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Terraform & Ansible 배포 플랫폼${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}경고: .env 파일이 없습니다.${NC}"
    if [ -f "env.example" ]; then
        echo -e "${YELLOW}env.example을 복사하여 .env 파일을 생성하세요.${NC}"
        echo -e "${YELLOW}  cp env.example .env${NC}"
    fi
    echo ""
fi

# 백엔드 설정 확인
echo -e "${GREEN}[1/4] 백엔드 환경 확인...${NC}"
cd backend

# Python 가상환경 확인
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Python 가상환경이 없습니다. 생성 중...${NC}"
    python3 -m venv venv
fi

# 가상환경 활성화
source venv/bin/activate

# 의존성 설치 확인
if [ ! -f "venv/.installed" ]; then
    echo -e "${YELLOW}백엔드 의존성 설치 중...${NC}"
    pip install -r requirements.txt
    touch venv/.installed
fi

# 환경 변수 로드 및 Terraform 변수 설정
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
    
    # Terraform 환경 변수 설정
    if [ ! -z "$PROXMOX_API_URL" ]; then
        export TF_VAR_proxmox_api_url="$PROXMOX_API_URL"
    fi
    if [ ! -z "$PROXMOX_API_TOKEN_ID" ]; then
        export TF_VAR_proxmox_api_token_id="$PROXMOX_API_TOKEN_ID"
    fi
    if [ ! -z "$PROXMOX_API_TOKEN_SECRET" ]; then
        export TF_VAR_proxmox_api_token_secret="$PROXMOX_API_TOKEN_SECRET"
    fi
    if [ ! -z "$PROXMOX_TLS_INSECURE" ]; then
        export TF_VAR_proxmox_tls_insecure="$PROXMOX_TLS_INSECURE"
    fi
fi

cd ..

# 프론트엔드 설정 확인
echo -e "${GREEN}[2/4] 프론트엔드 환경 확인...${NC}"
cd frontend

# node_modules 확인
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}프론트엔드 의존성 설치 중...${NC}"
    npm install
fi

cd ..

# 프로세스 정리 함수
cleanup() {
    echo ""
    echo -e "${YELLOW}프로세스 종료 중...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

# 시그널 핸들러 등록
trap cleanup SIGINT SIGTERM

# 백엔드 실행
echo -e "${GREEN}[3/4] 백엔드 서버 시작...${NC}"
cd backend
source venv/bin/activate
BACKEND_PORT=${BACKEND_PORT:-8000}
uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# 백엔드 시작 대기
sleep 3

# 백엔드 헬스체크
if curl -s http://localhost:$BACKEND_PORT/health > /dev/null; then
    echo -e "${GREEN}✓ 백엔드 서버 실행 중 (PID: $BACKEND_PID, 포트: $BACKEND_PORT)${NC}"
else
    echo -e "${RED}✗ 백엔드 서버 시작 실패${NC}"
    echo -e "${YELLOW}로그 확인: tail -f backend.log${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# 프론트엔드 실행
echo -e "${GREEN}[4/4] 프론트엔드 서버 시작...${NC}"
cd frontend
FRONTEND_PORT=${FRONTEND_PORT:-5173}
npm run dev -- --port $FRONTEND_PORT > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# 프론트엔드 시작 대기
sleep 5

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}서버 실행 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "프론트엔드: ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
echo -e "백엔드 API: ${GREEN}http://localhost:$BACKEND_PORT${NC}"
echo -e "API 문서:   ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
echo ""
echo -e "${YELLOW}로그 확인:${NC}"
echo -e "  백엔드:   tail -f backend.log"
echo -e "  프론트엔드: tail -f frontend.log"
echo ""
echo -e "${YELLOW}종료하려면 Ctrl+C를 누르세요.${NC}"
echo ""

# 프로세스 대기
wait
