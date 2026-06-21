"""Agent 业务服务"""

import logging
from typing import Optional

from core.domain.common import AgentType
from core.domain.agent import Agent
from core.domain.simulation import TopologyNode, TimelineEntry
from core.exceptions import SimulationNotFoundError, AgentNotFoundError, ValidationError
from engines.simulation_engine import SimulationEngine
import random

logger = logging.getLogger(__name__)


class AgentService:
    """Agent 业务服务"""

    def __init__(self, engine: SimulationEngine):
        self.engine = engine
        logger.info("[AgentService] 初始化完成")

    async def get_detail(self, simulation_id: str, agent_id: str) -> dict:
        """获取 Agent 详情"""
        logger.info("[AgentService] get_detail 开始, sim=%s, agent=%s", simulation_id, agent_id)
        result = await self.engine.get_agent_detail(simulation_id, agent_id)
        if not result:
            simulation = await self.engine.get_simulation(simulation_id)
            if not simulation:
                raise SimulationNotFoundError(simulation_id)
            raise AgentNotFoundError(agent_id)
        logger.info("[AgentService] get_detail 完成")
        return result

    async def modify(
        self,
        simulation_id: str,
        agent_id: str,
        field: str,
        value,
        reason: str = "",
    ) -> Agent:
        """修改 Agent 状态"""
        logger.info("[AgentService] modify 开始, sim=%s, agent=%s, field=%s", simulation_id, agent_id, field)
        simulation = await self.engine.get_simulation(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        agent = simulation.get_agent_by_id_or_name(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)

        if field == "sentiment":
            agent.sentiment = max(-1, min(1, float(value)))
        elif field == "goal":
            agent.goals.append(str(value))
        elif field == "goals":
            agent.goals = list(value) if isinstance(value, list) else [str(value)]
        elif field == "attribute" and isinstance(value, dict):
            key = value.get("key", "custom")
            agent.attributes[key] = str(value.get("value", ""))
        else:
            setattr(agent, field, value)

        await self.engine.repo.save(simulation)
        logger.info("[AgentService] modify 完成, field=%s", field)
        return agent

    async def add_agent(
        self,
        simulation_id: str,
        name: str,
        agent_type_str: str = "individual",
        description: str = "",
    ) -> Agent:
        """向推演中动态添加 Agent（自动调用 LLM 填充属性）"""
        logger.info("[AgentService] add_agent 开始, sim=%s, name=%s", simulation_id, name)
        simulation = await self.engine.get_simulation(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        try:
            agent_type = AgentType(agent_type_str)
        except ValueError:
            agent_type = AgentType.INDIVIDUAL

        # 调用 LLM 自动构建属性（使用用户提供的 description 或 simulation 描述作为上下文）
        context = description or simulation.description or simulation.name
        llm_attrs = await self.engine.build_agent_attributes(name, agent_type_str, context)

        agent = Agent(
            name=name,
            type=agent_type,
            description=description or llm_attrs["description"],
            attributes=llm_attrs["attributes"],
            keywords=llm_attrs["keywords"],
            is_actionable=llm_attrs["is_actionable"],
            personality=llm_attrs["personality"],
            goals=llm_attrs["goals"],
            created_round=simulation.current_round,
        )
        simulation.agents.append(agent)
        simulation.topology.nodes.append(TopologyNode(
            id=agent.id,
            label=agent.name,
            node_type="agent",
            agent_id=agent.id,
            x=random.uniform(-100, 100),
            y=random.uniform(-100, 100),
            metadata={"agent_type": agent.type},
        ))
        simulation.timeline.append(TimelineEntry(
            round=simulation.current_round,
            type="agent_added",
            actor=agent.name,
            action="加入推演",
            description=agent.description or f"{agent.name} 作为 {agent.type.value} 加入推演",
            details={"agent_id": agent.id, "agent_type": agent.type.value},
        ))
        await self.engine.repo.save(simulation)
        logger.info("[AgentService] add_agent 完成, id=%s, name=%s, desc=%s, goals=%d",
                     agent.id, name, bool(agent.description), len(agent.goals))
        return agent

    async def get_actions(self, simulation_id: str, agent_id: str) -> dict:
        """获取 Agent 行动历史"""
        logger.info("[AgentService] get_actions 开始, sim=%s, agent=%s", simulation_id, agent_id)
        simulation = await self.engine.get_simulation(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        agent = simulation.get_agent_by_id_or_name(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)

        logger.info("[AgentService] get_actions 完成, total=%d", len(agent.event_log))
        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "total_actions": len(agent.event_log),
            "actions": agent.event_log[-20:],
        }
