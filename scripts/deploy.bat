@echo off
REM ==========================================
REM Notion-AI Docker Deployment Script (Windows)
REM ==========================================

echo ==========================================
echo   Notion-AI Docker Deployment Script
echo ==========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist .env (
    echo ⚠️  .env file not found. Creating from .env.example...
    if exist .env.example (
        copy .env.example .env >nul
        echo ✅ .env file created
        echo 📝 Please edit .env and fill in your Notion account details
        echo    Then run this script again
        pause
        exit /b 0
    ) else (
        echo ❌ .env.example file not found
        pause
        exit /b 1
    )
)

REM Create required directories
echo 📁 Creating data directories...
if not exist data mkdir data
if not exist logs mkdir logs

REM Build image
echo 🔨 Building Docker image...
docker-compose build --no-cache

REM Start service
echo 🚀 Starting service...
docker-compose up -d

REM Wait for service to start
echo ⏳ Waiting for service to start...
timeout /t 5 /nobreak >nul

REM Check service status
echo.
echo 📊 Service status:
docker-compose ps

REM Health check
echo.
echo 🏥 Health check:
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ❌ Service failed to start. Check the logs:
    echo    docker-compose logs
) else (
    echo ✅ Service is running!
    echo.
    echo 🌐 Access URLs:
    echo    - Web UI: http://localhost:8000
    echo    - API docs: http://localhost:8000/docs
    echo    - Health check: http://localhost:8000/health
    echo.
    echo 📝 View logs:
    echo    docker-compose logs -f
    echo.
    echo 🛑 Stop service:
    echo    docker-compose down
)

echo.
echo ==========================================
echo   Deployment complete!
echo ==========================================
pause
