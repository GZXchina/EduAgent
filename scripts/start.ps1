# EduAgent 一键启动脚本
# 使用方法：右键点击此文件 -> 使用 PowerShell 运行
# 或者在 PowerShell 中执行: .\start.ps1

param(
    [switch]$SkipBuild,
    [switch]$SkipNpmInstall,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  EduAgent 一键启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Docker
Write-Host "[1/4] 检查Docker..." -ForegroundColor Yellow
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未安装Docker" -ForegroundColor Red
    Write-Host "请从 https://docker.com 下载安装Docker Desktop" -ForegroundColor Red
    exit 1
}

if (-not (docker ps 2>$null)) {
    Write-Host "错误: Docker未运行" -ForegroundColor Red
    Write-Host "请启动Docker Desktop后重试" -ForegroundColor Red
    exit 1
}
Write-Host "Docker 检查通过" -ForegroundColor Green

# 检查Docker Compose
Write-Host "[2/4] 检查Docker Compose..." -ForegroundColor Yellow
$composeVersion = docker compose version 2>$null
if (-not $composeVersion) {
    Write-Host "警告: docker compose 命令不可用，尝试 docker-compose" -ForegroundColor Yellow
    $global:USE_DOCKER_COMPOSE = $true
} else {
    Write-Host "Docker Compose 检查通过" -ForegroundColor Green
    $global:USE_DOCKER_COMPOSE = $false
}

# 前置检查
if (-not $SkipNpmInstall) {
    Write-Host "[3/4] 检查前端依赖..." -ForegroundColor Yellow
    $frontendPath = Join-Path $ProjectRoot "frontend"
    if (Test-Path (Join-Path $frontendPath "node_modules")) {
        Write-Host "前端依赖已安装" -ForegroundColor Green
    } else {
        Write-Host "前端依赖未安装，请先运行: cd frontend; npm install" -ForegroundColor Yellow
        Write-Host "或使用 -SkipNpmInstall 参数跳过" -ForegroundColor Yellow
    }
}

# 启动服务
Write-Host "[4/4] 启动Docker服务..." -ForegroundColor Yellow
Set-Location $ProjectRoot

if ($BackendOnly) {
    Write-Host "启动后端服务(仅后端模式)..." -ForegroundColor Cyan
    if ($global:USE_DOCKER_COMPOSE) {
        docker-compose -f docker/docker-compose.yml up -d postgres redis backend
    } else {
        docker compose -f docker/docker-compose.yml up -d postgres redis backend
    }
    Write-Host ""
    Write-Host "后端已启动: http://localhost:8000" -ForegroundColor Green
    Write-Host "API文档: http://localhost:8000/docs" -ForegroundColor Green
} else {
    Write-Host "启动全部服务..." -ForegroundColor Cyan
    if ($global:USE_DOCKER_COMPOSE) {
        if ($SkipBuild) {
            docker-compose -f docker/docker-compose.yml up -d
        } else {
            docker-compose -f docker/docker-compose.yml up --build -d
        }
    } else {
        if ($SkipBuild) {
            docker compose -f docker/docker-compose.yml up -d
        } else {
            docker compose -f docker/docker-compose.yml up --build -d
        }
    }
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  EduAgent 已成功启动!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "前端地址: http://localhost:8080" -ForegroundColor Cyan
    Write-Host "后端地址: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "API文档:  http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
}

# 等待服务启动
Start-Sleep -Seconds 2

# 检查服务状态
Write-Host ""
Write-Host "检查服务状态..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 5 2>$null
    if ($response.StatusCode -eq 200) {
        Write-Host "后端服务: 运行中" -ForegroundColor Green
    }
} catch {
    Write-Host "后端服务: 启动中..." -ForegroundColor Yellow
}

if (-not $BackendOnly) {
    try {
        $frontendResponse = Invoke-WebRequest -Uri "http://localhost:8080" -UseBasicParsing -TimeoutSec 5 2>$null
        if ($frontendResponse.StatusCode -eq 200) {
            Write-Host "前端服务: 运行中" -ForegroundColor Green
        }
    } catch {
        Write-Host "前端服务: 启动中..." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "使用 -SkipBuild 参数可跳过镜像构建加速启动" -ForegroundColor Gray
Write-Host "使用 -BackendOnly 参数可只启动后端服务" -ForegroundColor Gray