@echo off
chcp 65001 >nul 2>&1

cd /d "%~dp0.."

echo ========================================
echo   EduAgent Stop Script
echo ========================================
echo.

docker compose -f ..\docker\docker-compose.yml down

echo.
echo All services stopped
echo.
pause