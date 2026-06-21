#!/bin/bash
# EventSandbox backend_v1 启动脚本 (Linux/Mac)

cd "$(dirname "$0")"

# 使用项目 uv 虚拟环境启动服务（自动同步依赖）
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
