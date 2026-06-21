"""健康检查路由"""

import logging
import time

from fastapi import APIRouter, Depends

from app.dependencies import get_simulation_service, get_llm_client
from schemas.responses import HealthResponse
from services.simulation_service import SimulationService
from infrastructure.llm.client import AsyncLLMClient
from core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    llm: AsyncLLMClient = Depends(get_llm_client),
    sim_service: SimulationService = Depends(get_simulation_service),
):
    """健康检查"""
    settings = get_settings()
    try:
        sims = await sim_service.list_all(limit=1000)
        sim_count = sims["total"]
    except Exception as e:
        logger.warning("[Health] 获取推演数量失败: %s", e)
        sim_count = 0

    try:
        llm_connected = await llm.is_healthy()
    except Exception as e:
        logger.warning("[Health] LLM 健康检查失败: %s", e)
        llm_connected = False

    logger.info("[Health] 健康检查, llm_connected=%s, simulations=%d", llm_connected, sim_count)
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        llm_connected=llm_connected,
        llm_model=llm.get_model_name(),
        simulation_count=sim_count,
        timestamp=int(time.time() * 1000),
    )
