# EventSandbox backend_v1 启动脚本 (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$port = if ($env:PORT) { $env:PORT } else { 8000 }

# 使用项目 uv 虚拟环境启动服务（自动同步依赖）
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port $port --reload
