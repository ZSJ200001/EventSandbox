from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


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


class RelationType(str, Enum):
    COMPETITOR = "competitor"
    COOPERATIVE = "cooperative"
    SUPPLY = "supply"
    DEMAND = "demand"
    REGULATE = "regulate"
    INFLUENCE = "influence"
    NEUTRAL = "neutral"


class EventType(str, Enum):
    ACTION = "action"
    REACTION = "reaction"
    EXTERNAL = "external"
    INTERVENTION = "intervention"
    SYSTEM = "system"


class SimulationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class InterventionType(str, Enum):
    GLOBAL_PARAM = "global_param"
    AGENT_STATE = "agent_state"
    EXTERNAL_EVENT = "external_event"


class Belief(BaseModel):
    key: str
    value: str | int | float
    confidence: float = Field(ge=0, le=1)


class Relationship(BaseModel):
    target_agent_id: str
    type: RelationType
    strength: float = Field(ge=-1, le=1)


class Agent(BaseModel):
    id: str
    name: str
    type: AgentType
    description: str = ""
    personality: str = ""
    goals: list[str] = Field(default_factory=list)
    beliefs: list[Belief] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.ACTIVE
    position_x: Optional[float] = None
    position_y: Optional[float] = None

    class Config:
        use_enum_values = True


class EventImpact(BaseModel):
    affected_agents: list[str] = Field(default_factory=list)
    sentiment_change: dict[str, float] = Field(default_factory=dict)
    metric_changes: dict[str, float] = Field(default_factory=dict)


class Event(BaseModel):
    id: str
    type: EventType
    description: str
    timestamp: int
    round: int
    involved_agents: list[str] = Field(default_factory=list)
    impact: EventImpact = Field(default_factory=EventImpact)

    class Config:
        use_enum_values = True


class TopologyNode(BaseModel):
    id: str
    agent_id: str
    label: str
    type: AgentType

    class Config:
        use_enum_values = True


class TopologyEdge(BaseModel):
    source: str
    target: str
    relation: RelationType
    weight: float

    class Config:
        use_enum_values = True


class Topology(BaseModel):
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)


class SimulationMetrics(BaseModel):
    overall_sentiment: float = 0
    market_activity: float = 0
    cooperation_level: float = 0
    conflict_level: float = 0
    custom_metrics: dict[str, float] = Field(default_factory=dict)


class Simulation(BaseModel):
    id: str
    name: str
    description: str = ""
    agents: list[Agent] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    topology: Topology = Field(default_factory=Topology)
    rounds: int = 10
    current_round: int = 0
    status: SimulationStatus = SimulationStatus.PENDING
    metrics: SimulationMetrics = Field(default_factory=SimulationMetrics)
    start_time: Optional[int] = None
    end_time: Optional[int] = None

    class Config:
        use_enum_values = True


class Intervention(BaseModel):
    id: str
    type: InterventionType
    target: Optional[str] = None
    parameter: Optional[str] = None
    value: str | int | float | bool | dict
    timestamp: int
    round: int

    class Config:
        use_enum_values = True


class SimulationConfig(BaseModel):
    max_rounds: int = 10
    llm_model: str = "Qwen3-Coder-Next"
    temperature: float = 0.7
    knowledge_enabled: bool = True
    visualization_interval: int = 1
