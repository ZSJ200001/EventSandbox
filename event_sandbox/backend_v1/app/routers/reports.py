"""报告生成路由

POST /api/simulations/{simulation_id}/report
POST /api/simulations/{simulation_id}/report/baseline
GET  /api/simulations/{simulation_id}/report
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_simulation_engine, get_llm_client
from core.exceptions import EventSandboxError, SimulationNotFoundError
from engines.simulation_engine import SimulationEngine
from engines.report_engine import ReportEngine, BaselineReportEngine
from infrastructure.llm.client import AsyncLLMClient
from schemas.report_requests import GenerateReportRequest
from schemas.report_responses import GenerateReportResponse, ReportBundleResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulations", tags=["reports"])


def _handle_error(e: Exception) -> None:
    """统一异常转换"""
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, EventSandboxError):
        logger.warning("[API] 业务异常: %s", e.message)
        raise HTTPException(status_code=404 if e.code == "SIMULATION_NOT_FOUND" else 400, detail=e.message)
    logger.error("[API] 未知异常: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


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
        _handle_error(e)


@router.post("/{simulation_id}/report", response_model=GenerateReportResponse)
async def generate_report(
    simulation_id: str,
    request: GenerateReportRequest,
    engine: SimulationEngine = Depends(get_simulation_engine),
    llm_client: AsyncLLMClient = Depends(get_llm_client),
):
    """生成推演报告

    三层生成结构：逐 Agent 分析 → 整体局势描述 → 结论。
    结论会紧扣推演主线，直接回答主线提出的问题。
    生成后会自动持久化到推演数据中。
    """
    logger.info("[API] POST /api/simulations/%s/report", simulation_id)
    try:
        simulation = await engine.repo.get(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        report_engine = ReportEngine(llm_client=llm_client, repository=engine.repo)
        report = await report_engine.generate(simulation)
        return report
    except Exception as e:
        _handle_error(e)


@router.post("/{simulation_id}/report/baseline", response_model=GenerateReportResponse)
async def generate_baseline_report(
    simulation_id: str,
    engine: SimulationEngine = Depends(get_simulation_engine),
    llm_client: AsyncLLMClient = Depends(get_llm_client),
):
    """生成基线报告（纯 LLM 线性推演）

    基于初始事件信息，让单一 LLM 推演已发生的回合并生成分析报告。
    不涉及多 Agent 交互，用于与图谱推演报告进行对比。
    """
    logger.info("[API] POST /api/simulations/%s/report/baseline", simulation_id)
    try:
        simulation = await engine.repo.get(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        baseline_engine = BaselineReportEngine(llm_client=llm_client, repository=engine.repo)
        report = await baseline_engine.generate(simulation)
        return report
    except Exception as e:
        _handle_error(e)
