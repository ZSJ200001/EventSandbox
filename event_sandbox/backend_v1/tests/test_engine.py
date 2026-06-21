"""引擎层测试（需要 LLM 连接）"""

import pytest

from core.domain.common import SimulationStatus
from core.exceptions import SimulationNotFoundError, StepLockedError


@pytest.mark.asyncio
async def test_create_simulation(engine):
    """测试创建推演"""
    sim = await engine.create_simulation(
        name="奶茶涨价测试",
        description="测试推演",
        event_text="XX奶茶招牌产品涨价3元，引发市场连锁反应",
        rounds=3,
    )
    assert sim.id is not None
    assert sim.name == "奶茶涨价测试"
    assert len(sim.agents) > 0
    assert sim.status == SimulationStatus.PENDING


@pytest.mark.asyncio
async def test_step_simulation(engine):
    """测试执行一回合"""
    sim = await engine.create_simulation(
        name="测试",
        description="",
        event_text="某公司发布新产品",
        rounds=3,
    )
    assert len(sim.agents) > 0

    result = await engine.step(sim.id)
    simulation, new_events, updated_agents, action_results = result

    assert simulation.current_round == 1
    assert simulation.status == SimulationStatus.RUNNING
    assert len(action_results) == len(simulation.get_active_agents())


@pytest.mark.asyncio
async def test_get_nonexistent_simulation(engine):
    """测试获取不存在的推演"""
    result = await engine.get_simulation("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_delete_simulation(engine):
    """测试删除推演"""
    sim = await engine.create_simulation(
        name="删除测试",
        description="",
        event_text="测试事件",
        rounds=3,
    )
    result = await engine.delete_simulation(sim.id)
    assert result is True

    result2 = await engine.delete_simulation(sim.id)
    assert result2 is False
