"""Agent 领域模型（精简版）

去掉冗余字段：current_strategy, deep_profile, personality_traits, beliefs, resources, position_x/y
新增顶层 sentiment 字段替代 beliefs["sentiment"]
"""

import secrets
import time
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .common import AgentType


def _generate_short_id() -> str:
    """生成8位十六进制短ID"""
    return secrets.token_hex(4)


class MemoryEntry(BaseModel):
    """记忆条目"""

    round: int
    type: str = "observation"
    content: str
    emotional_valence: float = 0.0
    importance: float = Field(ge=0, le=1, default=0.5)
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class AgentMemory(BaseModel):
    """Agent 记忆系统"""

    short_term: list[MemoryEntry] = Field(default_factory=list)
    long_term: list[MemoryEntry] = Field(default_factory=list)
    max_short_term: int = 3

    def add_entry(self, entry: MemoryEntry) -> None:
        self.short_term.append(entry)
        if len(self.short_term) > self.max_short_term:
            self.short_term.sort(key=lambda x: x.importance, reverse=True)
            important = self.short_term[:3]
            self.long_term.extend(important)
            self.short_term = self.short_term[3:]

    def get_recent_context(self, limit: int = 5) -> str:
        recent = self.short_term[-limit:] if len(self.short_term) >= limit else self.short_term
        if not recent:
            return ""
        return "\n".join([f"[回合{r.round}] {r.content}" for r in recent])

    def get_formatted_memory(self) -> str:
        parts = []
        if self.long_term:
            parts.append("【长期记忆】" + "\n".join([f"- {m.content}" for m in self.long_term[-5:]]))
        if self.short_term:
            parts.append("【短期记忆】" + "\n".join([f"- {m.content}" for m in self.short_term[-5:]]))
        return "\n".join(parts) if parts else ""


class Agent(BaseModel):
    """Agent 实体"""

    id: str = Field(default_factory=_generate_short_id)
    name: str
    type: AgentType
    description: str = ""                          # 人设/特征描述（由LLM生成），同时用于展示和决策

    # 动态属性：不同类型实体有不同属性
    attributes: dict[str, str] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)

    # 推演参与属性
    is_actionable: bool = True
    controller_id: Optional[str] = None

    # 人设层（精简后只保留 personality 字符串）
    personality: str = ""                          # 性格标签，如"强硬、谨慎"
    goals: list[str] = Field(default_factory=list)

    # 状态
    sentiment: float = 0.0                         # 情绪值 -1 ~ 1，替代原 beliefs["sentiment"]
    emotional_intensity: float = Field(ge=0, le=1, default=0.5)

    # 记忆与日志
    event_log: list[dict] = Field(default_factory=list)
    memory: AgentMemory = Field(default_factory=AgentMemory)

    # 统计
    created_round: int = 0
    last_action_round: int = 0
    action_count: int = 0
