"""场景世界模型

场景感知推演架构（方案 C）的核心领域对象。
定义每个推演场景需要跟踪的世界状态、事件类型、终止条件等。
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class WorldEvent(BaseModel):
    """离散世界事件

    由 Agent 行动或外部干预触发，被记录到 world_events_history 中。
    例如足球比赛中的进球、犯规、红牌等。
    """

    type: str
    round: int
    actor: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScenarioWorldModel(BaseModel):
    """场景世界模型说明

    由 LLM 在创建推演时根据初始事件生成，告诉 Agent 该场景有哪些状态、
    什么行动会改变它们、什么时候结束、如何判定结果。
    """

    scenario_type: str = "generic"
    world_state_schema: dict[str, str] = Field(default_factory=dict)
    world_state_labels: dict[str, str] = Field(default_factory=dict)  # 字段名 -> 中文显示名
    event_types: list[str] = Field(default_factory=list)
    terminal_condition: str = ""
    action_grammar: str = ""
    initial_world_state: dict[str, Any] = Field(default_factory=dict)
    outcome_evaluation: str = ""
