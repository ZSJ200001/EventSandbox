from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum
from datetime import datetime


class AgentType(str, Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    COMPANY = "company"
    GOVERNMENT = "government"
    COMPETITOR = "competitor"
    SUPPLIER = "supplier"
    CONSUMER = "consumer"
    REGULATOR = "regulator"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INTERVENED = "intervened"
    ELIMINATED = "eliminated"  # 被淘汰/破产


class RelationType(str, Enum):
    COMPETITOR = "competitor"
    COOPERATIVE = "cooperative"
    SUPPLY = "supply"
    DEMAND = "demand"
    REGULATE = "regulate"
    INFLUENCE = "influence"
    OWNERSHIP = "ownership"  # 所有权/股权
    NEUTRAL = "neutral"


class EventType(str, Enum):
    ACTION = "action"          # Agent主动行动
    REACTION = "reaction"      # 对事件的反应
    EXTERNAL = "external"      # 外部事件
    INTERVENTION = "intervention"  # 用户干预
    SYSTEM = "system"         # 系统生成


class SimulationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class InterventionType(str, Enum):
    GLOBAL_PARAM = "global_param"
    AGENT_STATE = "agent_state"
    EXTERNAL_EVENT = "external_event"
    ADD_AGENT = "add_agent"
    REMOVE_AGENT = "remove_agent"
    MODIFY_RELATION = "modify_relation"


class ActionType(str, Enum):
    ATTACK = "attack"
    DEFEND = "defend"
    COOPERATE = "cooperate"
    NEGOTIATE = "negotiate"
    OBSERVE = "observe"
    WAIT = "wait"
    ADAPT = "adapt"


# ============== 结构化性格模型 (Big Five) ==============
class PersonalityTraits(BaseModel):
    openness: float = Field(ge=0, le=1, description="开放性 - 创造力、好奇心")
    conscientiousness: float = Field(ge=0, le=1, description="尽责性 - 自律、责任心")
    extraversion: float = Field(ge=0, le=1, description="外向性 - 社交能力")
    agreeableness: float = Field(ge=0, le=1, description="宜人性 - 合作、信任")
    neuroticism: float = Field(ge=0, le=1, description="神经质 - 情绪稳定性")

    def to_prompt_string(self) -> str:
        traits = []
        if self.openness > 0.7:
            traits.append("高开放性 - 富有创造力和好奇心")
        elif self.openness < 0.3:
            traits.append("低开放性 - 传统保守")

        if self.conscientiousness > 0.7:
            traits.append("高尽责性 - 做事有条理、负责任")
        elif self.conscientiousness < 0.3:
            traits.append("低尽责性 - 随意、不靠谱")

        if self.extraversion > 0.7:
            traits.append("高外向性 - 社交积极、活跃")
        elif self.extraversion < 0.3:
            traits.append("低外向性 - 内向安静")

        if self.agreeableness > 0.7:
            traits.append("高宜人性 - 信任他人、合作性强")
        elif self.agreeableness < 0.3:
            traits.append("低宜人性 - 怀疑、竞争性强")

        if self.neuroticism > 0.7:
            traits.append("高神经质 - 情绪波动大")
        elif self.neuroticism < 0.3:
            traits.append("低神经质 - 情绪稳定")

        return "；".join(traits) if traits else "中等水平"


# ============== Belief 信念 ==============
class Belief(BaseModel):
    key: str
    value: str | int | float
    confidence: float = Field(ge=0, le=1)
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    source: str = "observation"  # observation, inference, external, intervention
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


# ============== Relationship 关系 ==============
class Relationship(BaseModel):
    target_agent_id: str
    type: RelationType
    strength: float = Field(ge=-1, le=1)
    created_round: int = 0
    last_interaction_round: int = 0
    interaction_count: int = 0
    notes: str = ""


# ============== Memory 记忆 ==============
class MemoryEntry(BaseModel):
    """Agent 的记忆条目"""
    round: int
    type: str = "observation"  # observation, action, reaction, thought
    content: str
    emotional_valence: float = 0  # -1 负面 到 +1 正面
    importance: float = Field(ge=0, le=1, default=0.5)
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class AgentMemory(BaseModel):
    """Agent 的完整记忆系统"""
    short_term: list[MemoryEntry] = Field(default_factory=list)  # 最近 N 条
    long_term: list[MemoryEntry] = Field(default_factory=list)   # 重要记忆
    max_short_term: int = 20

    def add_entry(self, entry: MemoryEntry):
        self.short_term.append(entry)
        if len(self.short_term) > self.max_short_term:
            # 保留最重要的记忆到长期记忆
            self.short_term.sort(key=lambda x: x.importance, reverse=True)
            important = self.short_term[:3]
            self.long_term.extend(important)
            self.short_term = self.short_term[3:]

    def get_recent_context(self, limit: int = 5) -> str:
        """获取最近记忆作为上下文"""
        recent = self.short_term[-limit:] if len(self.short_term) >= limit else self.short_term
        if not recent:
            return ""
        return "\n".join([f"[回合{r.round}] {r.content}" for r in recent])

    def get_formatted_memory(self) -> str:
        """格式化所有记忆"""
        parts = []
        if self.long_term:
            parts.append("【长期记忆】" + "\n".join([f"- {m.content}" for m in self.long_term[-5:]]))
        if self.short_term:
            parts.append("【短期记忆】" + "\n".join([f"- {m.content}" for m in self.short_term[-5:]]))
        return "\n".join(parts) if parts else ""


# ============== Resource 资源 ==============
class Resource(BaseModel):
    """Agent 持有的资源"""
    name: str
    amount: float
    unit: str = ""
    change_log: list[dict] = Field(default_factory=list)


# ============== Agent ==============
class Agent(BaseModel):
    id: str
    name: str
    type: AgentType
    description: str = ""

    # 性格
    personality: str = ""  # 文字描述
    personality_traits: PersonalityTraits = Field(default_factory=PersonalityTraits)

    # 目标和策略
    goals: list[str] = Field(default_factory=list)
    current_strategy: str = ""

    # 信念和关系
    beliefs: list[Belief] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    # 状态
    status: AgentStatus = AgentStatus.ACTIVE
    emotional_intensity: float = Field(ge=0, le=1, default=0.5)  # 情绪激烈程度

    # 资源
    resources: list[Resource] = Field(default_factory=list)

    # 记忆
    memory: AgentMemory = Field(default_factory=AgentMemory)

    # 位置
    position_x: Optional[float] = None
    position_y: Optional[float] = None

    # 元数据
    created_round: int = 0
    last_action_round: int = 0
    action_count: int = 0

    class Config:
        use_enum_values = True

    def get_belief(self, key: str) -> Optional[Belief]:
        return next((b for b in self.beliefs if b.key == key and b.is_active), None)

    def update_belief(self, key: str, value, confidence: float = 1.0, source: str = "inference"):
        existing = self.get_belief(key)
        if existing:
            existing.value = value
            existing.confidence = confidence
            existing.timestamp = int(datetime.now().timestamp() * 1000)
            existing.source = source
        else:
            self.beliefs.append(Belief(key=key, value=value, confidence=confidence, source=source))

    def add_relationship(self, target_id: str, rel_type: RelationType, strength: float = 0):
        existing = next((r for r in self.relationships if r.target_agent_id == target_id), None)
        if existing:
            existing.type = rel_type
            existing.strength = max(-1, min(1, strength))
        else:
            self.relationships.append(Relationship(
                target_agent_id=target_id,
                type=rel_type,
                strength=max(-1, min(1, strength)),
                created_round=self.last_action_round
            ))

    def get_relation(self, target_id: str) -> Optional[Relationship]:
        return next((r for r in self.relationships if r.target_agent_id == target_id), None)


# ============== EventImpact ==============
class EventImpact(BaseModel):
    """事件影响"""
    affected_agents: list[str] = Field(default_factory=list)
    sentiment_change: dict[str, float] = Field(default_factory=dict)
    metric_changes: dict[str, float] = Field(default_factory=dict)
    resource_changes: dict[str, dict[str, float]] = Field(default_factory=dict)  # agent_id -> {resource_name: delta}
    relationship_changes: list[dict] = Field(default_factory=list)  # {from, to, type, delta}
    cascade_effects: list[str] = Field(default_factory=list)  # 连锁反应描述


# ============== Event ==============
class Event(BaseModel):
    id: str
    type: EventType
    description: str
    timestamp: int

    # 事件轮次
    round: int

    # 参与者
    involved_agents: list[str] = Field(default_factory=list)

    # 影响
    impact: EventImpact = Field(default_factory=EventImpact)

    # 事件属性
    consequence_severity: float = Field(ge=0, le=1, default=0.5)  # 后果严重程度
    duration: str = ""  # 即时/短期/中期/长期
    is_reversible: bool = True
    is_market_wide: bool = False  # 是否是市场范围事件

    # 行动结果
    action_taken: str = ""
    action_result: str = ""

    class Config:
        use_enum_values = True


# ============== Topology ==============
class TopologyNode(BaseModel):
    id: str
    agent_id: str
    label: str
    type: AgentType
    x: float = 0
    y: float = 0

    class Config:
        use_enum_values = True


class TopologyEdge(BaseModel):
    source: str
    target: str
    relation: RelationType
    weight: float = 0.5
    label: str = ""

    class Config:
        use_enum_values = True


class Topology(BaseModel):
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)


# ============== SimulationMetrics ==============
class SimulationMetrics(BaseModel):
    """仿真指标"""
    overall_sentiment: float = 0  # 整体情绪 -1 到 1
    market_activity: float = 0     # 市场活跃度 0 到 1
    cooperation_level: float = 0   # 合作水平 0 到 1
    conflict_level: float = 0      # 冲突程度 0 到 1
    stability: float = 1          # 稳定性 0 到 1
    innovation: float = 0         # 创新程度 0 到 1

    # 趋势指标
    sentiment_trend: float = 0    # 情绪趋势 -1 下降 到 1 上升
    activity_trend: float = 0     # 活跃度趋势

    # 额外指标
    custom_metrics: dict[str, float] = Field(default_factory=dict)

    def to_display_dict(self) -> dict:
        """转换为前端显示用的字典"""
        return {
            "overall_sentiment": self.overall_sentiment,
            "market_activity": self.market_activity,
            "cooperation_level": self.cooperation_level,
            "conflict_level": self.conflict_level,
            "stability": self.stability,
            "innovation": self.innovation,
        }


# ============== Simulation ==============
class Simulation(BaseModel):
    id: str
    name: str
    description: str = ""

    # 核心数据
    agents: list[Agent] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    topology: Topology = Field(default_factory=Topology)

    # 仿真配置
    rounds: int = 10
    current_round: int = 0

    # 状态
    status: SimulationStatus = SimulationStatus.PENDING
    metrics: SimulationMetrics = Field(default_factory=SimulationMetrics)

    # 全局参数
    global_sentiment: float = 0
    market_conditions: dict = Field(default_factory=dict)  # 市场整体状况

    # 时间
    start_time: Optional[int] = None
    end_time: Optional[int] = None

    # 干预历史
    interventions: list[dict] = Field(default_factory=list)

    # 关键节点标记
    critical_nodes: list[int] = Field(default_factory=list)  # 关键事件发生的回合

    class Config:
        use_enum_values = True

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return next((a for a in self.agents if a.id == agent_id), None)

    def get_active_agents(self) -> list[Agent]:
        return [a for a in self.agents if a.status in (AgentStatus.ACTIVE, AgentStatus.INTERVENED)]

    def add_event(self, event: Event):
        self.events.append(event)
        # 标记关键节点
        if event.consequence_severity > 0.7:
            self.critical_nodes.append(event.round)


# ============== Intervention ==============
class Intervention(BaseModel):
    id: str
    type: InterventionType
    target: Optional[str] = None  # agent_id or None for global
    parameter: Optional[str] = None
    value: str | int | float | bool | dict
    timestamp: int
    round: int
    delay: int = 0  # 延迟生效回合数
    is_active: bool = True

    class Config:
        use_enum_values = True


# ============== ActionResult ==============
class ActionResult(BaseModel):
    """Agent 行动结果"""
    agent_id: str
    action: str
    description: str
    success: bool = True
    sentiment_change: float = 0
    resource_changes: dict[str, float] = Field(default_factory=dict)
    target_effects: dict[str, float] = Field(default_factory=dict)  # 对目标的影响
    new_beliefs: list[Belief] = Field(default_factory=list)
    event: Optional[Event] = None


# ============== SimulationConfig ==============
class SimulationConfig(BaseModel):
    max_rounds: int = 10
    llm_model: str = "Qwen3-Coder-Next"
    temperature: float = 0.7
    knowledge_enabled: bool = True
    visualization_interval: int = 1

    # 高级配置
    enable_memory: bool = True
    enable_cascade: bool = True  # 连锁反应
    cascade_probability: float = 0.3
    enable_random_events: bool = True  # 随机事件
    random_event_probability: float = 0.1

    # 决策配置
    decision_iterations: int = 1  # 决策迭代次数
    use_few_shot: bool = True  # 使用 few-shot examples


# ============== Comparison ==============
class ComparisonResult(BaseModel):
    """对比结果"""
    with_intervention: dict
    without_intervention: dict
    differences: dict
    percentage_changes: dict
    key_insights: list[str]
