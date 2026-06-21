"""Agent 路由"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_agent_service, get_simulation_service
from schemas.requests import ModifyAgentRequest, AddAgentRequest
from schemas.responses import AgentDetailResponse, ModifyAgentResponse
from core.exceptions import EventSandboxError
from services.agent_service import AgentService
from services.simulation_service import SimulationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulations/{simulation_id}/agents", tags=["agents"])


def _handle_error(e: Exception) -> None:
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, EventSandboxError):
        logger.warning("[API] 业务异常: %s", e.message)
        raise HTTPException(status_code=404 if e.code in ("SIMULATION_NOT_FOUND", "AGENT_NOT_FOUND") else 400, detail=e.message)
    logger.error("[API] 未知异常: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent_detail(
    simulation_id: str,
    agent_id: str,
    service: AgentService = Depends(get_agent_service),
):
    """获取 Agent 详情"""
    logger.info("[API] GET /api/simulations/%s/agents/%s", simulation_id, agent_id)
    try:
        result = await service.get_detail(simulation_id, agent_id)
        return AgentDetailResponse(
            agent=result["agent"],
            recent_memory=result["recent_memory"],
            relationship_summary=result["relationship_summary"],
            action_history=result["action_history"],
            visible_actions=result["visible_actions"],
        )
    except Exception as e:
        _handle_error(e)


@router.post("/{agent_id}/modify", response_model=ModifyAgentResponse)
async def modify_agent(
    simulation_id: str,
    agent_id: str,
    request: ModifyAgentRequest,
    service: AgentService = Depends(get_agent_service),
):
    """修改 Agent 状态"""
    logger.info("[API] POST /api/simulations/%s/agents/%s/modify, field=%s", simulation_id, agent_id, request.field)
    try:
        agent = await service.modify(simulation_id, agent_id, request.field, request.value, request.reason)
        return ModifyAgentResponse(agent=agent, message=f"成功修改 {request.field}")
    except Exception as e:
        _handle_error(e)


@router.post("")
async def add_agent(
    simulation_id: str,
    request: AddAgentRequest,
    service: AgentService = Depends(get_agent_service),
    sim_service: SimulationService = Depends(get_simulation_service),
):
    """添加新 Agent"""
    logger.info("[API] POST /api/simulations/%s/agents, name=%s", simulation_id, request.name)
    try:
        agent = await service.add_agent(simulation_id, request.name, request.type, request.description)
        simulation = await sim_service.get(simulation_id)
        return {
            "success": True,
            "agent": agent,
            "message": f"新角色「{agent.name}」已添加",
            "simulation": simulation,
        }
    except Exception as e:
        _handle_error(e)


@router.get("/{agent_id}/actions")
async def get_agent_actions(
    simulation_id: str,
    agent_id: str,
    service: AgentService = Depends(get_agent_service),
):
    """获取 Agent 行动历史"""
    logger.info("[API] GET /api/simulations/%s/agents/%s/actions", simulation_id, agent_id)
    try:
        return await service.get_actions(simulation_id, agent_id)
    except Exception as e:
        _handle_error(e)
