#!/bin/bash
# EduAgent 一键启动脚本 (Linux/macOS)
# 使用方法: chmod +x start.sh && ./start.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 参数
SKIP_BUILD=false
BACKEND_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --backend-only)
            BACKEND_ONLY=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  EduAgent 一键启动脚本${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 检查Docker
echo -e "[1/4] ${YELLOW}检查Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未安装Docker${NC}"
    echo -e "${RED}请从 https://docker.com 下载安装Docker Desktop${NC}"
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo -e "${RED}错误: Docker未运行${NC}"
    echo -e "${RED}请启动Docker Desktop后重试${NC}"
    exit 1
fi
echo -e "${GREEN}Docker 检查通过${NC}"

# 检查Docker Compose
echo -e "[2/4] ${YELLOW}检查Docker Compose...${NC}"
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    echo -e "${GREEN}Docker Compose v2 检查通过${NC}"
elif docker-compose --version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    echo -e "${GREEN}Docker Compose v1 检查通过${NC}"
else
    echo -e "${RED}错误: 未安装Docker Compose${NC}"
    exit 1
fi

# 前置检查
echo -e "[3/4] ${YELLOW}检查前端依赖...${NC}"
if [ -d "frontend/node_modules" ]; then
    echo -e "${GREEN}前端依赖已安装${NC}"
else
    echo -e "${YELLOW}前端依赖未安装${NC}"
    echo -e "${YELLOW}建议先运行: cd frontend && npm install${NC}"
fi

# 启动服务
echo -e "[4/4] ${YELLOW}启动Docker服务...${NC}"

if [ "$BACKEND_ONLY" = true ]; then
    echo -e "${CYAN}启动后端服务(仅后端模式)...${NC}"
    if [ "$SKIP_BUILD" = true ]; then
        $COMPOSE_CMD -f docker/docker-compose.yml up -d postgres redis backend
    else
        $COMPOSE_CMD -f docker/docker-compose.yml up --build -d postgres redis backend
    fi
    echo ""
    echo -e "${GREEN}后端已启动: http://localhost:8000${NC}"
    echo -e "${GREEN}API文档: http://localhost:8000/docs${NC}"
else
    echo -e "${CYAN}启动全部服务...${NC}"
    if [ "$SKIP_BUILD" = true ]; then
        $COMPOSE_CMD -f docker/docker-compose.yml up -d
    else
        $COMPOSE_CMD -f docker/docker-compose.yml up --build -d
    fi

    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${GREEN}  EduAgent 已成功启动!${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    echo -e "${CYAN}前端地址: http://localhost:8080${NC}"
    echo -e "${CYAN}后端地址: http://localhost:8000${NC}"
    echo -e "${CYAN}API文档:  http://localhost:8000/docs${NC}"
    echo ""
    echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
fi

# 等待服务启动
sleep 2

# 检查服务状态
echo ""
echo -e "${YELLOW}检查服务状态...${NC}"
if curl -s http://localhost:8000/api/health &> /dev/null; then
    echo -e "${GREEN}后端服务: 运行中${NC}"
else
    echo -e "${YELLOW}后端服务: 启动中...${NC}"
fi

if [ "$BACKEND_ONLY" = false ]; then
    if curl -s http://localhost:8080 &> /dev/null; then
        echo -e "${GREEN}前端服务: 运行中${NC}"
    else
        echo -e "${YELLOW}前端服务: 启动中...${NC}"
    fi
fi

echo ""
echo -e "${NC}使用 --skip-build 参数可跳过镜像构建加速启动"
echo -e "${NC}使用 --backend-only 参数可只启动后端服务"