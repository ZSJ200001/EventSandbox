"""LLM 相关数据结构"""

from pydantic import BaseModel, Field
from typing import Optional, Any


class LLMConfig(BaseModel):
    """LLM 配置"""

    api_base: str
    api_key: str
    default_model: str
    timeout: float = 120.0
    max_tokens: int = 2048
    temperature: float = 0.7
    enable_few_shot: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0


class LLMMessage(BaseModel):
    """LLM 消息"""

    role: str
    content: str


class LLMResponse(BaseModel):
    """LLM 响应"""

    content: str
    model: str
    usage: dict = Field(default_factory=dict)
    finish_reason: str = ""


class AgentDecisionOutput(BaseModel):
    """Agent 决策输出结构"""

    action: str = "观望/不行动"
    reasoning: str = ""
    expected_outcome: str = ""
    sentiment_change: float = 0.0
    target_agents: list[str] = Field(default_factory=list)
    action_description: str = ""
    relation_changes: list[dict] = Field(default_factory=list)


class WorldStateUpdateOutput(BaseModel):
    """世界状态汇总输出"""

    world_state_updates: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class ExtractedEntity(BaseModel):
    """提取出的实体"""

    name: str
    type: str = "entity"           # LLM 返回的原始类型字符串
    reason: str = ""               # 提取理由


class EntityExtractionOutput(BaseModel):
    """实体提取输出"""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    is_complete: bool = True       # LLM 是否认为已提取完整
    reasoning: str = ""            # 判断依据


class EntityAttributesOutput(BaseModel):
    """实体属性构建输出"""

    description: str = ""          # 核心描述（人设/特征）
    attributes: dict[str, str] = Field(default_factory=dict)  # 动态属性
    keywords: list[str] = Field(default_factory=list)          # 关键词标签
    is_actionable: bool = True     # 是否可自主行动
    controller: str = ""           # 若不可行动，控制者名称


class ExtractedRelationship(BaseModel):
    """提取出的关系"""

    source: str                    # 源实体名称
    target: str                    # 目标实体名称
    relation: str = ""             # 关系标签
    description: str = ""          # 关系描述


class EventRelation(BaseModel):
    """事件与实体的关系"""

    target: str                    # 目标实体名称
    relation: str = ""             # 关系标签（2-4字）
    description: str = ""          # 角色描述


class RelationshipExtractionOutput(BaseModel):
    """关系提取输出"""

    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    event_relations: list[EventRelation] = Field(default_factory=list)  # 事件与实体的关系
    event_summary: str = ""        # 事件摘要
    scene_ontology: str = ""       # 场景本体摘要


class ScenarioWorldModelOutput(BaseModel):
    """场景世界模型提取输出（方案 C）"""

    scenario_type: str = "generic"
    world_state_schema: dict[str, str] = Field(default_factory=dict)
    world_state_labels: dict[str, str] = Field(default_factory=dict)  # 字段名 -> 中文显示名
    event_types: list[str] = Field(default_factory=list)
    terminal_condition: str = ""
    action_grammar: str = ""
    initial_world_state: dict[str, Any] = Field(default_factory=dict)
    outcome_evaluation: str = ""


class ExternalImpactOutput(BaseModel):
    """外部事件影响分析输出"""

    relation_updates: list[dict] = Field(default_factory=list)
    agent_logs: dict[str, str] = Field(default_factory=dict)
    world_state_updates: dict[str, Any] = Field(default_factory=dict)
    events: list[dict] = Field(default_factory=list)


class MainLinePressureOutput(BaseModel):
    """主线压力输出：每个核心 Agent 应感受到的主线压力"""

    pressures: dict[str, str] = Field(default_factory=dict)  # agent_name -> pressure_text


class InterventionOptionsOutput(BaseModel):
    """干预选项输出"""

    event_options: list[dict] = Field(default_factory=list)
    agent_options: list[dict] = Field(default_factory=list)
    env_options: list[dict] = Field(default_factory=list)


