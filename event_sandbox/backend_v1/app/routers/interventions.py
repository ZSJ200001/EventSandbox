"""干预路由"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_intervention_service, get_simulation_engine
from schemas.requests import QuickInterventionRequest
from schemas.responses import BaseResponse
from core.exceptions import EventSandboxError
from services.intervention_service import InterventionService
from engines.simulation_engine import SimulationEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["interventions"])


def _handle_error(e: Exception) -> None:
    """统一异常转换"""
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, EventSandboxError):
        logger.warning("[API] 业务异常: %s", e.message)
        raise HTTPException(status_code=404 if e.code == "SIMULATION_NOT_FOUND" else 400, detail=e.message)
    logger.error("[API] 未知异常: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@router.get("/interventions/options")
async def get_intervention_options(
    simulation_id: str,
    option_type: str = "global",
    agent_id: Optional[str] = None,
    service: InterventionService = Depends(get_intervention_service),
):
    """生成干预选项"""
    logger.info("[API] GET /api/interventions/options, sim=%s, type=%s", simulation_id, option_type)
    try:
        return await service.generate_options(simulation_id, option_type, agent_id)
    except Exception as e:
        _handle_error(e)


@router.post("/interventions/quick", response_model=BaseResponse)
async def quick_intervene(
    request: QuickInterventionRequest,
    engine: SimulationEngine = Depends(get_simulation_engine),
):
    """快速干预 —— 直接注入事件，不推进回合"""
    logger.info("[API] POST /api/interventions/quick, sim=%s", request.simulation_id)
    try:
        event_values = {
            "regulatory_warning": "【突发事件】监管部门约谈企业负责人，要求解释近期市场行为",
            "competitor_price_cut": "【突发事件】竞争对手宣布降价15%，市场格局生变",
            "negative_news": "【突发事件】媒体曝光企业产品存在质量问题，舆论哗然",
            "promotion": "【突发事件】企业启动全品促销，活动力度空前",
            "policy_change": "【政策变化】政府出台新法规，对行业产生重大影响",
            "market_boom": "【市场变化】整体市场繁荣期到来，消费者购买力增强",
        }
        description = request.custom_value or event_values.get(request.quick_option, "干预事件")
        await engine.inject_event(request.simulation_id, description)
        return BaseResponse(message="快速干预已应用")
    except Exception as e:
        _handle_error(e)
