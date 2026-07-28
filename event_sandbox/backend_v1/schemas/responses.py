"""API 响应模型"""

from pydantic import BaseModel, Field
from typing import Optional, Any

from core.domain.simulation import Simulation, SimulationConfig, SimulationMetrics, Topology
from core.domain.agent import Agent
from core.domain.event import Event
from core.domain.common import SimulationStatus


class BaseResponse(BaseModel):
    success: bool = True
    message: str = ""


class CreateTaskResponse(BaseResponse):
    task_id: str
    status: str = "pending"
    logs: list[dict] = Field(default_factory=list)


class CreateTaskStatusResponse(BaseResponse):
    task_id: str
    status: str = "pending"
    logs: list[dict] = Field(default_factory=list)
    simulation: Optional[Simulation] = None
    error: str = ""
    created_at: float = 0
    updated_at: float = 0


class CreateSimulationResponse(BaseResponse):
    simulation: Simulation
    generated_agents: list[Agent] = Field(default_factory=list)
    topology: Topology


class StepSimulationResponse(BaseResponse):
    simulation: Simulation
    new_events: list[Event] = Field(default_factory=list)
    updated_agents: list[Agent] = Field(default_factory=list)
    action_results: list[dict] = Field(default_factory=list)
    round_summary: str = ""


class InterventionResponse(BaseResponse):
    intervention_id: str = ""
    affected_agents: list[str] = Field(default_factory=list)
    predicted_effects: dict = Field(default_factory=dict)


class InjectEventResponse(BaseResponse):
    simulation: Simulation
    event: Event
    affected_agent_count: int = 0



class AgentDetailResponse(BaseResponse):
    agent: Agent
    recent_memory: str = ""
    relationship_summary: list[dict] = Field(default_factory=list)
    action_history: list[dict] = Field(default_factory=list)
    visible_actions: list[dict] = Field(default_factory=list)


class ModifyAgentResponse(BaseResponse):
    agent: Agent


class SimulationStateResponse(BaseResponse):
    simulation: Simulation
    active_agent_count: int = 0
    event_count: int = 0
    recent_events: list[Event] = Field(default_factory=list)
    agent_summaries: list[dict] = Field(default_factory=list)
    is_being_stepped: bool = False  # 当前是否正在执行 step（用于前端禁用推进按钮）


class BatchStepResponse(BaseResponse):
    task_id: str
    simulation_id: str
    status: str = "pending"
    steps_requested: int = 0
    steps_executed: int = 0
    events_generated: int = 0
    current_round: int = 0
    stop_reason: str = ""
    error: str = ""


class BatchStepStatusResponse(BaseResponse):
    task_id: str
    simulation_id: str
    status: str = "pending"
    steps_requested: int = 0
    steps_executed: int = 0
    events_generated: int = 0
    current_round: int = 0
    stop_reason: str = ""
    error: str = ""
    created_at: float = 0
    updated_at: float = 0


class SimulationSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    status: SimulationStatus
    current_round: int = 0
    rounds: int = 0
    agent_count: int = 0
    event_count: int = 0
    created_at: int = 0


class ListSimulationsResponse(BaseResponse):
    simulations: list[SimulationSummary] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = ""
    llm_connected: bool = False
    llm_model: str = ""
    simulation_count: int = 0
    timestamp: int = 0


class DeleteSimulationResponse(BaseResponse):
    pass


class PauseSimulationResponse(BaseResponse):
    simulation: Simulation


class NewsItem(BaseModel):
    title: str = ""
    time: str = ""
    keywords: str = ""
    description: str = ""


class SearchNewsResponse(BaseResponse):
    query: str = ""
    total: int = 0
    results: list[NewsItem] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    code: str = ""
    simulation_id: Optional[str] = None
