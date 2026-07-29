"""报告生成路由

POST /api/simulations/{simulation_id}/report        — 提交推演报告生成任务
POST /api/simulations/{simulation_id}/report/baseline — 提交基线报告生成任务
GET  /api/simulations/{simulation_id}/report           — 获取已生成报告
GET  /api/simulations/{simulation_id}/report/status/{task_id} — 查询报告任务进度
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_simulation_engine, get_llm_client, get_simulation_service
from core.exceptions import SimulationNotFoundError
from app.error_handlers import handle_api_error
from engines.simulation_engine import SimulationEngine
from infrastructure.llm.client import AsyncLLMClient
from services.simulation_service import SimulationService
from schemas.report_requests import GenerateReportRequest
from schemas.report_responses import GenerateReportResponse, ReportBundleResponse
from schemas.responses import ReportTaskResponse, ReportTaskStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulations", tags=["reports"])


@router.get("/{simulation_id}/report", response_model=ReportBundleResponse)
async def get_report(
    simulation_id: str,
    engine: SimulationEngine = Depends(get_simulation_engine),
):
    """获取已生成的推演报告和基线报告（如果未生成则对应字段为 None）"""
    logger.info("[API] GET /api/simulations/%s/report", simulation_id)
    try:
        simulation = await engine.repo.get(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        report = None
        baseline_report = None

        if simulation.report:
            report = GenerateReportResponse.model_validate(simulation.report)
        if simulation.baseline_report:
            baseline_report = GenerateReportResponse.model_validate(simulation.baseline_report)

        return ReportBundleResponse(report=report, baseline_report=baseline_report)
    except Exception as e:
        handle_api_error(e)


@router.post("/{simulation_id}/report", response_model=ReportTaskResponse)
async def generate_report(
    simulation_id: str,
    request: GenerateReportRequest,
    service: SimulationService = Depends(get_simulation_service),
):
    """提交推演报告生成任务（异步）

    立即返回 task_id，前端轮询 GET /api/simulations/{id}/report/status/{task_id} 获取进度。
    生成后自动持久化到推演数据中。
    """
    logger.info("[API] POST /api/simulations/%s/report", simulation_id)
    try:
        task = await service.generate_report_async(simulation_id)
        return ReportTaskResponse(
            task_id=task["task_id"],
            status=task["status"],
            logs=task["logs"],
        )
    except Exception as e:
        handle_api_error(e)


@router.get("/{simulation_id}/report/status/{task_id}", response_model=ReportTaskStatusResponse)
async def get_report_status(
    simulation_id: str,
    task_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """查询报告生成任务进度。前端轮询此接口获取实时日志和结果。"""
    logger.info("[API] GET /api/simulations/%s/report/status/%s", simulation_id, task_id)
    try:
        task = await service.get_report_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"报告任务 {task_id} 不存在")
        return ReportTaskStatusResponse(
            task_id=task["task_id"],
            status=task["status"],
            logs=task["logs"],
            report=task.get("report"),
            error=task.get("error", ""),
            created_at=task.get("created_at", 0),
            updated_at=task.get("updated_at", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_api_error(e)


@router.post("/{simulation_id}/report/baseline", response_model=ReportTaskResponse)
async def generate_baseline_report(
    simulation_id: str,
    service: SimulationService = Depends(get_simulation_service),
):
    """提交基线报告生成任务（异步）

    立即返回 task_id，前端轮询 GET /api/simulations/{id}/report/status/{task_id} 获取进度。
    基线报告基于初始事件由单一 LLM 进行线性推演。
    """
    logger.info("[API] POST /api/simulations/%s/report/baseline", simulation_id)
    try:
        task = await service.generate_baseline_report_async(simulation_id)
        return ReportTaskResponse(
            task_id=task["task_id"],
            status=task["status"],
            logs=task["logs"],
        )
    except Exception as e:
        handle_api_error(e)
