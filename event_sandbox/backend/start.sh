@echo off
REM EventSandbox Backend Startup Script

echo ========================================
echo EventSandbox Backend Server
echo ========================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher
    pause
    exit /b 1
)

REM Set environment variables
set LLM_API_BASE=http://101.251.216.47/8411/v1
set LLM_API_KEY=sk-empty
set DEFAULT_MODEL=Qwen3-Coder-Next
set PORT=8000

REM Install dependencies if needed
echo.
echo Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install fastapi uvicorn pydantic httpx networkx
)

REM Start the server
echo.
echo Starting server on port %PORT%...
echo API documentation will be available at http://localhost:%PORT%/docs
echo.

cd /d "%~dp0"
python -m uvicorn api.main:app --host 0.0.0.0 --port %PORT% --reload

pause
