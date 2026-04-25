from pydantic import BaseModel, Field
from typing import Optional
from .entities import (
    Simulation,
    Agent,
    Topology,
    SimulationConfig,
    Intervention,
    SimulationMetrics,
    Event,
)


class CreateSimulationRequest(BaseModel):
    name: str
    description: str = ""
    event_text: str
    config: Optional[SimulationConfig] = None


class CreateSimulationResponse(BaseModel):
    simulation: Simulation
    generated_agents: list[Agent]
    topology: Topology


class StepSimulationRequest(BaseModel):
    simulation_id: str
    intervention: Optional[Intervention] = None


class StepSimulationResponse(BaseModel):
    simulation: Simulation
    new_events: list[Event]
    updated_agents: list[Agent]


class InterventionRequest(BaseModel):
    simulation_id: str
    intervention: Intervention


class InterventionResponse(BaseModel):
    success: bool
    message: str
    updated_agents: list[Agent]


class CompareReport(BaseModel):
    simulation_id: str
    without_intervention: SimulationMetrics
    with_intervention: SimulationMetrics
    comparison: list[dict]  # [{metric, difference, percentage_change}]


class SimulationStateResponse(BaseModel):
    simulation: Simulation
    recent_events: list[Event] = Field(default_factory=list)
    agent_states: dict[str, dict] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_connected: bool
