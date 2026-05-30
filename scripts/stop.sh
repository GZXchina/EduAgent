#!/bin/bash
# EduAgent 停止脚本 (Linux/macOS)

echo "========================================"
echo "  EduAgent 停止服务"
echo "========================================"
echo ""

if docker compose version &> /dev/null; then
    docker compose -f docker/docker-compose.yml down
elif docker-compose --version &> /dev/null; then
    docker-compose -f docker/docker-compose.yml down
else
    echo "错误: 未安装Docker Compose"
    exit 1
fi

echo ""
echo "所有服务已停止"