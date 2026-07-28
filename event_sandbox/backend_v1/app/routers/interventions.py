"""干预路由"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends

from app.dependencies import get_intervention_service
from app.error_handlers import handle_api_error
from services.intervention_service import InterventionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["interventions"])


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
        handle_api_error(e)
