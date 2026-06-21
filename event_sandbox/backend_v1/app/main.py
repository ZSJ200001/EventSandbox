"""FastAPI 应用入口。

全局配置：
- 结构化日志（含时间戳）
- 全局异常处理器
- CORS
- 路由挂载
"""

import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.exceptions import EventSandboxError
from app.dependencies import lifespan_init, lifespan_shutdown
from app.routers import simulations, agents, interventions, health, retrieval, reports


def _setup_logging() -> None:
    """配置全局日志"""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(settings.log_format)

    root = logging.getLogger()
    root.setLevel(level)

    # 清理旧 handler（热重载时）
    for h in root.handlers[:]:
        root.removeHandler(h)

    # 标准输出
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    # 文件输出
    import os
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "backend.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.info("[Main] 日志系统初始化完成, level=%s, log_file=%s", settings.log_level, log_file)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    _setup_logging()
    logging.info("[Main] 应用启动中...")
    await lifespan_init()
    logging.info("[Main] 应用启动完成")
    yield
    logging.info("[Main] 应用关闭中...")
    await lifespan_shutdown()
    logging.info("[Main] 应用关闭完成")


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="可干预的智能事件推演沙盘 API (v1)",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== 全局异常处理器 ==============
@app.exception_handler(EventSandboxError)
async def business_exception_handler(request: Request, exc: EventSandboxError):
    status_code = 404 if exc.code in ("SIMULATION_NOT_FOUND", "AGENT_NOT_FOUND") else 400
    logging.warning("[ExceptionHandler] 业务异常: code=%s, message=%s, path=%s", exc.code, exc.message, request.url.path)
    return JSONResponse(
        status_code=status_code,
        content={"error": exc.message, "code": exc.code, "detail": ""},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logging.error("[ExceptionHandler] 未捕获异常: %s, path=%s", exc, request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "code": "INTERNAL_ERROR", "detail": f"{type(exc).__name__}: {str(exc)}"},
    )


# ============== 路由挂载 ==============
app.include_router(health.router)
app.include_router(simulations.router)
app.include_router(agents.router)
app.include_router(interventions.router)
app.include_router(retrieval.router)
app.include_router(reports.router)


# ============== 根路径 ==============
@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
