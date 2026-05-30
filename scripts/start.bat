@echo off
chcp 65001 >nul 2>&1

REM Auto-detect docker-compose.yml by searching upward from script location
set "COMPOSE_FILE="
set "SEARCH_DIR=%~dp0"

:search_loop
if exist "%SEARCH_DIR%docker-compose.yml" (
    set "COMPOSE_FILE=%SEARCH_DIR%docker-compose.yml"
    goto :found
)
if exist "%SEARCH_DIR%docker\docker-compose.yml" (
    set "COMPOSE_FILE=%SEARCH_DIR%docker\docker-compose.yml"
    goto :found
)
REM Move up one level
for %%I in ("%SEARCH_DIR%..") do set "PARENT=%%~fI\"
if /i "%PARENT%"=="%SEARCH_DIR%" goto :not_found
set "SEARCH_DIR=%PARENT%"
goto :search_loop

:not_found
echo Error: docker-compose.yml not found in any parent directory
pause
exit /b 1

:found
echo ========================================
echo   EduAgent Startup Script
echo ========================================
echo.
echo Compose file: %COMPOSE_FILE%
echo.

echo [1/3] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed or not in PATH
    pause
    exit /b 1
)
echo Docker found
echo.

echo [2/3] Starting services...
set DOCKER_BUILDKIT=0
set COMPOSE_BAKE=false

docker compose -f "%COMPOSE_FILE%" up -d

if errorlevel 1 (
    echo Initial start failed, attempting rebuild...
    docker compose -f "%COMPOSE_FILE%" up --build -d
)

echo.
echo [3/3] Checking status...
timeout /t 3 /nobreak >nul

docker compose -f "%COMPOSE_FILE%" ps

echo.
echo ========================================
echo   EduAgent Started!
echo ========================================
echo.
echo Frontend: http://localhost:8080
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
pause