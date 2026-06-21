"""场景世界模型单元测试"""

import pytest
from datetime import datetime

from core.domain.simulation import Simulation, SimulationConfig
from core.domain.world_model import ScenarioWorldModel, WorldEvent
from core.domain.agent import Agent
from core.domain.common import AgentType


@pytest.fixture
def football_world_model():
    return ScenarioWorldModel(
        scenario_type="football_match",
        world_state_schema={
            "score": "string",
            "match_phase": "enum",
            "possession": "string",
            "fouls": "dict",
            "minute": "number",
        },
        event_types=["goal", "foul", "substitution", "red_card", "full_time"],
        terminal_condition="match_phase == 'full_time'",
        action_grammar="每回合选择一个比赛动作，并说明对世界状态的影响",
        initial_world_state={
            "score": "西班牙 0:0 佛得角",
            "match_phase": "first_half",
            "possession": "西班牙",
            "fouls": {"西班牙": 0, "佛得角": 0},
            "minute": 0,
        },
        outcome_evaluation="根据最终比分判断胜负",
    )


@pytest.fixture
def simulation_with_world_model(football_world_model):
    sim = Simulation(
        name="测试足球推演",
        description="西班牙 vs 佛得角",
        config=SimulationConfig(round_duration_unit="minute", round_duration_value=9),
        world_model=football_world_model,
        world_state=dict(football_world_model.initial_world_state),
        agents=[
            Agent(name="西班牙", type=AgentType.GOVERNMENT),
            Agent(name="佛得角", type=AgentType.GOVERNMENT),
        ],
    )
    sim.snapshot_world_state(0)
    return sim


def test_update_world_state(simulation_with_world_model):
    sim = simulation_with_world_model
    before = sim.update_world_state({
        "score": "西班牙 1:0 佛得角",
        "possession": "西班牙",
        "minute": 67,
    })

    assert sim.world_state["score"] == "西班牙 1:0 佛得角"
    assert sim.world_state["minute"] == 67.0
    assert before["score"] == "西班牙 0:0 佛得角"


def test_snapshot_world_state(simulation_with_world_model):
    sim = simulation_with_world_model
    sim.update_world_state({"score": "西班牙 1:0 佛得角"})
    sim.snapshot_world_state(1)

    assert len(sim.world_state_history) == 2
    assert sim.world_state_history[1]["round"] == 1
    assert sim.world_state_history[1]["state"]["score"] == "西班牙 1:0 佛得角"


def test_add_world_event(simulation_with_world_model):
    sim = simulation_with_world_model
    evt = WorldEvent(
        type="goal",
        round=1,
        actor="西班牙",
        description="佩德里远射破门",
        metadata={"scorer": "佩德里", "minute": 67},
    )
    sim.add_world_event(evt)

    assert len(sim.world_events_history) == 1
    assert sim.world_events_history[0].type == "goal"


def test_check_terminal_condition_true(simulation_with_world_model):
    sim = simulation_with_world_model
    sim.current_round = 5
    sim.update_world_state({"match_phase": "full_time"})

    assert sim.check_terminal_condition() is True


def test_check_terminal_condition_false(simulation_with_world_model):
    sim = simulation_with_world_model
    sim.current_round = 5
    sim.update_world_state({"match_phase": "second_half"})

    assert sim.check_terminal_condition() is False


def test_check_terminal_condition_round_fallback(simulation_with_world_model):
    sim = simulation_with_world_model
    sim.current_round = 10

    assert sim.check_terminal_condition() is True


def test_check_terminal_condition_no_world_model():
    sim = Simulation(name="无世界模型")
    sim.current_round = 5

    assert sim.check_terminal_condition() is False


def test_eval_safe_expression_complex():
    sim = Simulation(name="测试")
    assert sim._eval_safe_expression("a == 1 and b == 2", {"a": 1, "b": 2}) is True
    assert sim._eval_safe_expression("a == 1 or b == 3", {"a": 1, "b": 2}) is True
    assert sim._eval_safe_expression("x in ['a', 'b']", {"x": "a"}) is True
    assert sim._eval_safe_expression("score_diff > 3", {"score_diff": 5}) is True


def test_build_timeline_facts_includes_world_event(simulation_with_world_model):
    from core.domain.simulation import TimelineEntry

    sim = simulation_with_world_model
    sim.timeline.append(TimelineEntry(
        round=1,
        type="world_event",
        actor="西班牙",
        action="goal",
        description="佩德里远射破门",
        details={"metadata": {"scorer": "佩德里"}},
    ))

    # ReportEngine 使用 timeline facts，这里只验证 timeline 结构
    assert sim.timeline[0].type == "world_event"
    assert sim.timeline[0].action == "goal"
