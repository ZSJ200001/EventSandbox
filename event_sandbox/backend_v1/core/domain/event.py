"""事件领域模型"""

import secrets
from pydantic import BaseModel, Field
from .common import EventType


def _generate_short_id() -> str:
    """生成8位十六进制短ID"""
    return secrets.token_hex(4)


class EventImpact(BaseModel):
    """事件影响"""

    affected_agents: list[str] = Field(default_factory=list)
    sentiment_change: dict[str, float] = Field(default_factory=dict)
    metric_changes: dict[str, float] = Field(default_factory=dict)
    resource_changes: dict[str, dict[str, float]] = Field(default_factory=dict)
    relationship_changes: list[dict] = Field(default_factory=list)
    cascade_effects: list[str] = Field(default_factory=list)


class Event(BaseModel):
    """事件实体"""

    id: str = Field(default_factory=_generate_short_id)
    type: EventType
    description: str
    timestamp: int
    round: int
    involved_agents: list[str] = Field(default_factory=list)
    impact: EventImpact = Field(default_factory=EventImpact)

    consequence_severity: float = Field(ge=0, le=1, default=0.5)
    duration: str = ""
    is_reversible: bool = True
    is_market_wide: bool = False

    action_taken: str = ""
    action_result: str = ""
