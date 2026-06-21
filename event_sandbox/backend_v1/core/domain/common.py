"""公共枚举与基础类型"""

from enum import Enum


class AgentType(str, Enum):
    """Agent 实体类型 —— 保留核心4种，新增扩展类型，无法归类时 fallback 到 ENTITY"""

    # 核心可行动类型
    COMPANY = "company"
    GOVERNMENT = "government"
    ORGANIZATION = "organization"
    INDIVIDUAL = "individual"

    # 扩展类型
    LOCATION = "location"         # 地点、区域、场所
    MILITARY = "military"         # 军事单位、舰队、军团
    VEHICLE = "vehicle"           # 载具、飞机、舰船、设备

    # 兜底类型
    ENTITY = "entity"             # 无法归类时归入此类


class EventType(str, Enum):
    """事件类型"""

    ACTION = "action"
    REACTION = "reaction"
    EXTERNAL = "external"
    INTERVENTION = "intervention"
    SYSTEM = "system"


class SimulationStatus(str, Enum):
    """推演状态"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class InterventionType(str, Enum):
    """干预类型"""

    AGENT_STATE = "agent_state"
    EXTERNAL_EVENT = "external_event"
    ADD_AGENT = "add_agent"
    REMOVE_AGENT = "remove_agent"
