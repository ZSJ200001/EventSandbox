# EventSandbox Backend Startup Script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EventSandbox Backend Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.10 or higher" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Set environment variables
$env:LLM_API_BASE = "http://101.251.216.47/8411/v1"
$env:LLM_API_KEY = "sk-empty"
$env:DEFAULT_MODEL = "Qwen3-Coder-Next"
$env:PORT = "8000"

# Install dependencies if needed
Write-Host ""
Write-Host "Checking dependencies..." -ForegroundColor Yellow

$dependencies = @("fastapi", "uvicorn", "pydantic", "httpx", "networkx")
foreach ($dep in $dependencies) {
    $installed = pip show $dep 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing $dep..." -ForegroundColor Yellow
        pip install $dep -q
    }
}

# Change to script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Start the server
Write-Host ""
Write-Host "Starting server on port $env:PORT..." -ForegroundColor Green
Write-Host "API documentation: http://localhost:$env:PORT/docs" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn api.main:app --host 0.0.0.0 --port $env:PORT --reload
