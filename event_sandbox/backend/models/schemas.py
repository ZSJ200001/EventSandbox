from pydantic import BaseModel, Field
from typing import Optional, Any
from .entities import (
    Simulation,
    Agent,
    Topology,
    SimulationConfig,
    Intervention,
    SimulationMetrics,
    Event,
    SimulationStatus,
    AgentType,
    EventType,
    ComparisonResult,
)


# ============== 创建推演 ==============
class CreateSimulationRequest(BaseModel):
    name: str = Field(..., description="推演名称")
    description: str = Field(default="", description="推演描述")
    event_text: str = Field(..., description="初始事件描述")
    config: Optional[SimulationConfig] = None
    rounds: int = Field(default=10, ge=1, le=100, description="推演轮数")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "奶茶涨价事件推演",
                "description": "分析XX奶茶涨价后的市场反应",
                "event_text": "XX奶茶招牌产品涨价3元，引发市场连锁反应",
                "rounds": 10
            }
        }


class CreateSimulationResponse(BaseModel):
    simulation: Simulation
    generated_agents: list[Agent]
    topology: Topology
    message: str = "推演场景创建成功"


# ============== 推演控制 ==============
class StepSimulationRequest(BaseModel):
    simulation_id: str
    intervention: Optional[Intervention] = None
    steps: int = Field(default=1, ge=1, le=10, description="连续执行的步数")


class StepSimulationResponse(BaseModel):
    simulation: Simulation
    new_events: list[Event]
    updated_agents: list[Agent]
    action_results: list[dict] = Field(default_factory=list, description="各Agent的行动结果")
    round_summary: str = ""


# ============== 干预 ==============
class InterventionRequest(BaseModel):
    simulation_id: str
    intervention: Intervention


class InterventionResponse(BaseModel):
    success: bool
    message: str
    intervention_id: str
    affected_agents: list[str] = Field(default_factory=list)
    predicted_effects: dict = Field(default_factory=dict)


# ============== 快速干预预设 ==============
class QuickInterventionRequest(BaseModel):
    simulation_id: str
    intervention_type: str = Field(..., description="event/agent/env/add_agent/modify_relation")
    quick_option: str = Field(..., description="预设选项key")
    custom_value: Optional[str] = Field(None, description="自定义值")
    target_agent_id: Optional[str] = Field(None, description="目标Agent ID")


class QuickInterventionOption(BaseModel):
    """快速干预选项"""
    key: str
    label: str
    description: str
    icon: str = ""
    default_severity: float = 0.5


# ============== Agent 操作 ==============
class AgentDetailRequest(BaseModel):
    simulation_id: str
    agent_id: str


class AgentDetailResponse(BaseModel):
    agent: Agent
    recent_memory: str = ""
    relationship_summary: list[dict] = Field(default_factory=list)
    action_history: list[dict] = Field(default_factory=list)


class ModifyAgentRequest(BaseModel):
    simulation_id: str
    agent_id: str
    field: str = Field(..., description="要修改的字段")
    value: Any = Field(..., description="新值")
    reason: str = Field(default="", description="修改原因")


class ModifyAgentResponse(BaseModel):
    success: bool
    agent: Agent
    message: str


# ============== 事件详情 ==============
class EventDetailRequest(BaseModel):
    simulation_id: str
    event_id: str


class EventDetailResponse(BaseModel):
    event: Event
    involved_agents_detail: list[Agent] = Field(default_factory=list)
    impact_analysis: dict = Field(default_factory=dict)


# ============== 对比分析 ==============
class CompareScenariosRequest(BaseModel):
    simulation_id: str
    intervention: Intervention
    steps: int = Field(default=5, ge=1, le=20, description="对比步数")
    compare_metrics: list[str] = Field(
        default=["overall_sentiment", "market_activity", "cooperation_level", "conflict_level"],
        description="要对比的指标"
    )


class CompareScenariosResponse(BaseModel):
    simulation_id: str
    baseline_metrics: SimulationMetrics
    with_intervention_metrics: SimulationMetrics
    metric_deltas: dict[str, float]
    metric_percentage_changes: dict[str, float]
    timeline_comparison: list[dict] = Field(default_factory=list)
    key_insights: list[str] = Field(default_factory=list)
    conclusion: str = ""


# ============== 仿真状态 ==============
class SimulationStateRequest(BaseModel):
    simulation_id: str
    include_events: bool = True
    include_agents: bool = True
    include_metrics: bool = True
    recent_events_limit: int = Field(default=20, ge=0)


class SimulationStateResponse(BaseModel):
    simulation: Simulation
    active_agent_count: int = 0
    event_count: int = 0
    recent_events: list[Event] = Field(default_factory=list)
    agent_summaries: list[dict] = Field(default_factory=list)


# ============== 批量操作 ==============
class BatchStepRequest(BaseModel):
    simulation_id: str
    steps: int = Field(default=5, ge=1, le=50)
    stop_on_condition: Optional[str] = Field(
        None,
        description="停止条件: sentiment_threshold/conflict_threshold/completion"
    )
    sentiment_threshold: float = Field(default=0.8, description="情绪阈值")
    conflict_threshold: float = Field(default=0.8, description="冲突阈值")


class BatchStepResponse(BaseModel):
    simulation: Simulation
    steps_executed: int
    events_generated: list[Event]
    final_metrics: SimulationMetrics
    stop_reason: str = ""


# ============== 知识图谱查询 ==============
class KnowledgeQueryRequest(BaseModel):
    simulation_id: str
    entity_id: Optional[str] = None
    query_type: str = Field(default="neighbors", description="neighbors/constraints/context")
    relation_filter: Optional[str] = None


class KnowledgeQueryResponse(BaseModel):
    query_type: str
    results: dict | list[dict]


# ============== 健康检查 ==============
class HealthResponse(BaseModel):
    status: str
    version: str
    llm_connected: bool
    llm_model: str = ""
    simulation_count: int = 0
    timestamp: int = 0


# ============== 仿真列表 ==============
class ListSimulationsRequest(BaseModel):
    status: Optional[SimulationStatus] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0)


class SimulationSummary(BaseModel):
    id: str
    name: str
    description: str
    status: SimulationStatus
    current_round: int
    rounds: int
    agent_count: int
    event_count: int
    created_at: int = 0


class ListSimulationsResponse(BaseModel):
    simulations: list[SimulationSummary]
    total: int
    limit: int
    offset: int


# ============== 删除仿真 ==============
class DeleteSimulationRequest(BaseModel):
    simulation_id: str


class DeleteSimulationResponse(BaseModel):
    success: bool
    message: str


# ============== 暂停/恢复 ==============
class PauseSimulationRequest(BaseModel):
    simulation_id: str


class PauseSimulationResponse(BaseModel):
    success: bool
    simulation: Simulation
    message: str


# ============== 错误响应 ==============
class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    simulation_id: Optional[str] = None
