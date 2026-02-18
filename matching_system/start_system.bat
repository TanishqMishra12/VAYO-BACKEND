@echo off
REM Startup Script for AI-Powered Community Matching System
REM This script starts all required services in separate windows

echo ========================================
echo AI-Powered Community Matching System
echo Startup Script
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then run: .\venv\Scripts\activate
    echo Then run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please copy .env.example to .env and configure your API keys
    echo Run: copy .env.example .env
    echo Then edit .env with your actual keys
    pause
    exit /b 1
)

echo [1/4] Checking Redis...
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Redis not responding. Starting Redis...
    start "Redis Server" cmd /k "redis-server"
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] Redis is running
)

echo.
echo [2/4] Starting FastAPI Server with WebSocket...
start "FastAPI + WebSocket Server" cmd /k "cd /d %~dp0 && venv\Scripts\activate && uvicorn matching_system.api:socket_app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo.
echo [3/4] Starting Celery Worker...
start "Celery Worker" cmd /k "cd /d %~dp0 && venv\Scripts\activate && celery -A matching_system.celery_tasks worker --loglevel=info --pool=solo"

timeout /t 2 /nobreak >nul

echo.
echo [4/4] Opening API Documentation...
timeout /t 5 /nobreak >nul
start http://localhost:8000/docs

echo.
echo ========================================
echo All services started!
echo ========================================
echo.
echo FastAPI Server: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Health Check: http://localhost:8000/api/v1/health
echo.
echo Press Ctrl+C in each window to stop services
echo.
pause
