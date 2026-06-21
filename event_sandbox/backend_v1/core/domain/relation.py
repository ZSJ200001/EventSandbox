"""关系边领域模型"""

import secrets
from pydantic import BaseModel, Field


def _generate_short_id() -> str:
    """生成8位十六进制短ID"""
    return secrets.token_hex(4)


class RelationEdge(BaseModel):
    """全局关系边 —— 记录两个实体之间的语义关系

    每条边是有向的、独立的对象，A->B 和 B->A 是两条不同的边。
    同一对 source-target 之间可以有多个不同 relation 标签的边。
    """

    id: str = Field(default_factory=_generate_short_id)
    source_id: str
    target_id: str
    relation: str = ""  # 这条边自己的关系标签
    description: str = ""  # 当前关系描述（最新值）
    polarity: str = ""  # "positive" | "negative" | "neutral"
    created_round: int = 0
    last_interaction_round: int = 0
    interaction_count: int = 0
    evolution_history: list[dict] = Field(default_factory=list)  # 变更快照历史
