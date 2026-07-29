"""推演路由"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_simulation_service, get_simulation_engine
from schemas.requests import CreateSimulationRequest, StepSimulationRequest, BatchStepRequest, InjectEventRequest, UpdateSimulationRequest
from schemas.responses import (
    CreateTaskResponse,
    CreateTaskStatusResponse,
    CreateSimulationResponse,
    StepSimulationResponse,
    SimulationStateResponse,
    BatchStepResponse,
    BatchStepStatusResponse,
    ListSimulationsResponse,
    SimulationSummary,
    DeleteSimulationResponse,
    PauseSimulationResponse,
    InjectEventResponse,
)
from engines.simulation_engine import SimulationEngine
from services.simulation_service import SimulationService
from app.error_handlers import handle_api_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.post("", response_model=CreateTaskResponse)
async def create_simulation(
    request: CreateSimulationRequest,
    service: SimulationService = Depends(get_simulation_service),
):
    """创建推演（异步任务，立即返回 task_id，前端轮询获取进度）"""
    logger.info("[API] POST /api/simulations, name=%s", request.name)
    try:
        task = await service.create(
            name=request.name,
            description=request.description,
            event_text=request.event_text,
            config=request.config,
            rounds=request.rounds,
        )
        return CreateTaskResponse(
            task_id=task["task_id"],
            status=task["status"],
            logs=task["logs"],
        )
    except Exception as e:
        handle_api_error(e)


@router.get("/create/{task_id}", response_model=CreateTaskStatusResponse)
async def get_create_status(
    task_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """查询创建推演任务进度。前端轮询此接口获取实时日志和结果。"""
    logger.info("[API] GET /api/simulations/create/%s", task_id)
    try:
        task = await service.get_create_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"创建任务 {task_id} 不存在")
        return CreateTaskStatusResponse(
            task_id=task["task_id"],
            status=task["status"],
            logs=task["logs"],
            simulation=task.get("simulation"),
            error=task.get("error", ""),
            created_at=task.get("created_at", 0),
            updated_at=task.get("updated_at", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_api_error(e)


@router.get("", response_model=ListSimulationsResponse)
async def list_simulations(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    service: SimulationService = Depends(get_simulation_service),
):
    """列出推演"""
    logger.info("[API] GET /api/simulations, status=%s, limit=%d, offset=%d", status, limit, offset)
    try:
        result = await service.list_all(status=status, limit=limit, offset=offset)
        summaries = [
            SimulationSummary(
                id=s.id,
                name=s.name,
                description=s.description,
                status=s.status,
                current_round=s.current_round,
                rounds=s.rounds,
                agent_count=s.agent_count or len(s.agents),
                event_count=s.event_count or len(s.events),
            )
            for s in result["simulations"]
        ]
        return ListSimulationsResponse(
            simulations=summaries,
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
        )
    except Exception as e:
        handle_api_error(e)


@router.get("/{simulation_id}", response_model=SimulationStateResponse)
async def get_simulation(
    simulation_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """获取推演详情"""
    logger.info("[API] GET /api/simulations/%s", simulation_id)
    try:
        simulation = await service.get(simulation_id)
        recent_events = simulation.events[-20:] if len(simulation.events) > 20 else simulation.events
        agent_summaries = []
        for agent in simulation.agents:
            rel_count = len(simulation.get_relations_of(agent.id))
            agent_summaries.append({
                "id": agent.id,
                "name": agent.name,
                "type": agent.type,
                "is_actionable": agent.is_actionable,
                "sentiment": agent.sentiment,
                "goals_count": len(agent.goals),
                "relationship_count": rel_count,
            })

        return SimulationStateResponse(
            simulation=simulation,
            active_agent_count=len(simulation.get_active_agents()),
            event_count=len(simulation.events),
            recent_events=recent_events,
            agent_summaries=agent_summaries,
            is_being_stepped=service.is_stepping(simulation_id),
        )
    except Exception as e:
        handle_api_error(e)


@router.post("/{simulation_id}/step", response_model=StepSimulationResponse)
async def step_simulation(
    simulation_id: str,
    request: StepSimulationRequest,
    service: SimulationService = Depends(get_simulation_service),
):
    """执行一回合"""
    logger.info("[API] POST /api/simulations/%s/step", simulation_id)
    try:
        result = await service.step(simulation_id)
        return StepSimulationResponse(
            simulation=result["simulation"],
            new_events=result["new_events"],
            updated_agents=result["updated_agents"],
            action_results=result["action_results"],
            round_summary=result["round_summary"],
        )
    except Exception as e:
        handle_api_error(e)


@router.post("/{simulation_id}/events", response_model=InjectEventResponse)
async def inject_event(
    simulation_id: str,
    request: InjectEventRequest,
    engine: SimulationEngine = Depends(get_simulation_engine),
):
    """事件注入 —— 即刻生效，不推进回合"""
    logger.info("[API] POST /api/simulations/%s/events", simulation_id)
    try:
        simulation = await engine.inject_event(simulation_id, request.description)
        return InjectEventResponse(
            simulation=simulation,
            event=simulation.events[-1],
            affected_agent_count=sum(
                1 for a in simulation.agents
                if a.event_log and a.event_log[-1].get("round") == simulation.current_round and a.event_log[-1].get("type") == "外部干预"
            ),
        )
    except Exception as e:
        handle_api_error(e)


@router.post("/{simulation_id}/batch-step", response_model=BatchStepResponse)
async def batch_step(
    simulation_id: str,
    request: BatchStepRequest,
    service: SimulationService = Depends(get_simulation_service),
):
    """启动批量推演异步任务"""
    logger.info("[API] POST /api/simulations/%s/batch-step, steps=%d", simulation_id, request.steps)
    try:
        task = await service.batch_step(
            simulation_id=simulation_id,
            steps=request.steps,
            stop_on_condition=request.stop_on_condition,
            conflict_threshold=request.conflict_threshold,
        )
        return BatchStepResponse(
            task_id=task["task_id"],
            simulation_id=task["simulation_id"],
            status=task["status"],
            steps_requested=task["steps_requested"],
            steps_executed=task["steps_executed"],
            events_generated=task["events_generated"],
            current_round=task["current_round"],
            stop_reason=task["stop_reason"],
            error=task["error"],
            logs=task.get("logs", []),
        )
    except Exception as e:
        handle_api_error(e)


@router.get("/{simulation_id}/batch-status/{task_id}", response_model=BatchStepStatusResponse)
async def get_batch_status(
    simulation_id: str,
    task_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """查询批量推演任务状态"""
    logger.info("[API] GET /api/simulations/%s/batch-status/%s", simulation_id, task_id)
    try:
        task = await service.get_batch_status(simulation_id, task_id)
        return BatchStepStatusResponse(
            task_id=task["task_id"],
            simulation_id=task["simulation_id"],
            status=task["status"],
            steps_requested=task["steps_requested"],
            steps_executed=task["steps_executed"],
            events_generated=task["events_generated"],
            current_round=task["current_round"],
            stop_reason=task["stop_reason"],
            error=task["error"],
            created_at=task["created_at"],
            updated_at=task["updated_at"],
            logs=task.get("logs", []),
        )
    except Exception as e:
        handle_api_error(e)


@router.post("/{simulation_id}/pause", response_model=PauseSimulationResponse)
async def pause_simulation(
    simulation_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """暂停推演"""
    logger.info("[API] POST /api/simulations/%s/pause", simulation_id)
    try:
        simulation = await service.pause(simulation_id)
        return PauseSimulationResponse(simulation=simulation, message="推演已暂停")
    except Exception as e:
        handle_api_error(e)


@router.post("/{simulation_id}/resume", response_model=PauseSimulationResponse)
async def resume_simulation(
    simulation_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """恢复推演"""
    logger.info("[API] POST /api/simulations/%s/resume", simulation_id)
    try:
        simulation = await service.resume(simulation_id)
        return PauseSimulationResponse(simulation=simulation, message="推演已恢复")
    except Exception as e:
        handle_api_error(e)


@router.patch("/{simulation_id}", response_model=SimulationStateResponse)
async def update_simulation(
    simulation_id: str,
    request: UpdateSimulationRequest,
    service: SimulationService = Depends(get_simulation_service),
):
    """更新推演属性（名称、描述等）"""
    logger.info("[API] PATCH /api/simulations/%s, name=%s, description=%s", simulation_id, request.name, request.description)
    try:
        simulation = await service.update(simulation_id, name=request.name, description=request.description)
        recent_events = simulation.events[-20:] if len(simulation.events) > 20 else simulation.events
        return SimulationStateResponse(
            simulation=simulation,
            active_agent_count=len(simulation.get_active_agents()),
            event_count=len(simulation.events),
            recent_events=recent_events,
            agent_summaries=[],
            is_being_stepped=service.is_stepping(simulation_id),
        )
    except Exception as e:
        handle_api_error(e)


@router.delete("/{simulation_id}", response_model=DeleteSimulationResponse)
async def delete_simulation(
    simulation_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """删除推演"""
    logger.info("[API] DELETE /api/simulations/%s", simulation_id)
    try:
        result = await service.delete(simulation_id)
        if not result:
            raise HTTPException(status_code=404, detail="推演不存在")
        return DeleteSimulationResponse(message="推演已删除")
    except Exception as e:
        handle_api_error(e)
