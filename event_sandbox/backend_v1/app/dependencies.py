"""FastAPI 依赖注入容器。

集中管理所有服务的生命周期，替代全局变量。
"""

import logging
from typing import AsyncGenerator

from core.config import get_settings
from infrastructure.llm.client import AsyncLLMClient
from infrastructure.persistence.file import FileBasedSimulationRepository
from infrastructure.retrieval.news_retriever import NewsRetriever
from engines.simulation_engine import SimulationEngine
from services.simulation_service import SimulationService
from services.agent_service import AgentService
from services.intervention_service import InterventionService

logger = logging.getLogger(__name__)

# 应用生命周期内持有的单例
_llm_client: AsyncLLMClient | None = None
_simulation_engine: SimulationEngine | None = None
_simulation_service: SimulationService | None = None
_agent_service: AgentService | None = None
_intervention_service: InterventionService | None = None
_news_retriever: NewsRetriever | None = None


async def lifespan_init() -> None:
    """应用启动时初始化所有依赖"""
    global _llm_client, _simulation_engine, _simulation_service, _agent_service, _intervention_service, _news_retriever

    logger.info("[Dependencies] 初始化开始")
    _llm_client = AsyncLLMClient()
    repo = FileBasedSimulationRepository()
    _simulation_engine = SimulationEngine(llm_client=_llm_client, repository=repo)
    _simulation_service = SimulationService(_simulation_engine)
    _agent_service = AgentService(_simulation_engine)
    _intervention_service = InterventionService(_simulation_engine, _llm_client)
    _news_retriever = NewsRetriever()
    logger.info("[Dependencies] 初始化完成")


async def lifespan_shutdown() -> None:
    """应用关闭时清理资源"""
    global _llm_client, _news_retriever
    logger.info("[Dependencies] 关闭开始")
    if _llm_client:
        await _llm_client.close()
        _llm_client = None
    if _news_retriever:
        await _news_retriever.close()
        _news_retriever = None
    logger.info("[Dependencies] 关闭完成")


async def get_llm_client() -> AsyncLLMClient:
    if _llm_client is None:
        raise RuntimeError("LLMClient 未初始化")
    return _llm_client


async def get_simulation_engine() -> SimulationEngine:
    if _simulation_engine is None:
        raise RuntimeError("SimulationEngine 未初始化")
    return _simulation_engine


async def get_simulation_service() -> SimulationService:
    if _simulation_service is None:
        raise RuntimeError("SimulationService 未初始化")
    return _simulation_service


async def get_agent_service() -> AgentService:
    if _agent_service is None:
        raise RuntimeError("AgentService 未初始化")
    return _agent_service


async def get_intervention_service() -> InterventionService:
    if _intervention_service is None:
        raise RuntimeError("InterventionService 未初始化")
    return _intervention_service


async def get_news_retriever() -> NewsRetriever:
    if _news_retriever is None:
        raise RuntimeError("NewsRetriever 未初始化")
    return _news_retriever
