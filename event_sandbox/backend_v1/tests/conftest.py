"""pytest 配置与共享 fixture"""

import pytest
import pytest_asyncio

from infrastructure.llm.client import AsyncLLMClient
from infrastructure.persistence.memory import InMemorySimulationRepository
from engines.simulation_engine import SimulationEngine
from services.simulation_service import SimulationService
from services.agent_service import AgentService
from services.intervention_service import InterventionService
from engines.report_engine import ReportEngine


@pytest_asyncio.fixture
async def repo():
    """内存仓库"""
    return InMemorySimulationRepository()


@pytest_asyncio.fixture
async def llm_client():
    """LLM 客户端（使用真实配置）"""
    client = AsyncLLMClient()
    yield client
    await client.close()


@pytest_asyncio.fixture
async def engine(repo, llm_client):
    """推演引擎"""
    return SimulationEngine(llm_client=llm_client, repository=repo)


@pytest_asyncio.fixture
async def sim_service(engine):
    """推演服务"""
    return SimulationService(engine)


@pytest_asyncio.fixture
async def agent_service(engine):
    """Agent 服务"""
    return AgentService(engine)


@pytest_asyncio.fixture
async def intervention_service(engine, llm_client):
    """干预服务"""
    return InterventionService(engine, llm_client)


@pytest_asyncio.fixture
async def report_engine(llm_client, repo):
    """报告生成引擎"""
    return ReportEngine(llm_client=llm_client, repository=repo)
