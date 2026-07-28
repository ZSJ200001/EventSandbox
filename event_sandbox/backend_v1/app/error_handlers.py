"""统一错误处理。

所有路由共享一个 _handle_error，确保响应格式一致：
{"error": message, "code": code, "detail": ""}
"""

import logging

from fastapi import HTTPException

from core.exceptions import EventSandboxError

logger = logging.getLogger(__name__)


def handle_api_error(e: Exception) -> None:
    """统一异常转换。所有路由层捕获异常后调用此函数抛出标准 HTTPException。

    返回格式始终为 {"detail": message}，由 FastAPI 自动序列化。
    业务异常的 code 信息通过 HTTP 状态码体现：
    - 404: SIMULATION_NOT_FOUND, AGENT_NOT_FOUND
    - 423: STEP_LOCKED
    - 400: 其他业务异常
    - 500: 未知异常
    """
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, EventSandboxError):
        logger.warning("[API] 业务异常: code=%s, message=%s", e.code, e.message)
        if e.code == "STEP_LOCKED":
            raise HTTPException(status_code=423, detail=e.message)
        if e.code in ("SIMULATION_NOT_FOUND", "AGENT_NOT_FOUND"):
            raise HTTPException(status_code=404, detail=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    logger.error("[API] 未知异常: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")
