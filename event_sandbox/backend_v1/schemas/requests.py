"""API 请求模型"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

from core.domain.simulation import SimulationConfig


class CreateSimulationRequest(BaseModel):
    name: str = Field(..., description="推演名称")
    description: str = Field(default="", description="推演描述")
    event_text: str = Field(..., description="初始事件描述")
    config: Optional[SimulationConfig] = None
    rounds: int = Field(default=10, ge=1, le=100)

    # 时间切片配置（创建后不可修改）
    start_datetime: Optional[datetime] = Field(default=None, description="推演起始时间，默认当前时间")
    round_duration_value: float = Field(default=1.0, ge=0.1, description="每回合时长数值")
    round_duration_unit: str = Field(default="round", description="时间单位：minute/hour/day/week/month/quarter/year/round")


class StepSimulationRequest(BaseModel):
    simulation_id: str
    intervention: Optional[dict] = None
    steps: int = Field(default=1, ge=1, le=10)


class InterventionRequest(BaseModel):
    simulation_id: str
    intervention: dict


class ModifyAgentRequest(BaseModel):
    simulation_id: str
    agent_id: str
    field: str
    value: Any
    reason: str = ""


class BatchStepRequest(BaseModel):
    simulation_id: str
    steps: int = Field(default=5, ge=1, le=50)
    stop_on_condition: Optional[str] = None
    conflict_threshold: float = Field(default=0.8)


class AddAgentRequest(BaseModel):
    name: str
    type: str = Field(default="individual")
    description: str = ""


class InjectEventRequest(BaseModel):
    description: str = Field(..., description="事件描述")


class SearchNewsRequest(BaseModel):
    query: str = Field(..., description="查询文本（事件描述）")
    topk: int = Field(default=10, ge=1, le=50, description="返回条数")
