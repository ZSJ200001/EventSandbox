"""干预业务服务"""

import logging

from core.exceptions import LLMError, SimulationNotFoundError
from engines.simulation_engine import SimulationEngine
from infrastructure.llm.client import AsyncLLMClient

logger = logging.getLogger(__name__)


class InterventionService:
    """干预业务服务"""

    def __init__(self, engine: SimulationEngine, llm_client: AsyncLLMClient):
        self.engine = engine
        self.llm = llm_client
        logger.info("[InterventionService] 初始化完成")

    async def generate_options(
        self,
        simulation_id: str,
        option_type: str = "global",
        agent_id: str | None = None,
    ) -> dict:
        """生成干预选项（仅支持全局事件/环境选项）"""
        logger.info("[InterventionService] generate_options 开始, sim=%s, type=%s", simulation_id, option_type)

        simulation = await self.engine.get_simulation(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        def _to_options(items):
            return [
                {
                    "key": item.get("key", f"opt_{i}"),
                    "label": item.get("label", "干预"),
                    "description": item.get("description", ""),
                    "icon": "",
                    "value": item.get("value", item.get("description", "")),
                }
                for i, item in enumerate(items)
            ]

        if option_type != "global":
            logger.warning("[InterventionService] 不支持的 option_type=%s，回退到 global", option_type)

        agents_data = [{"name": a.name, "type": str(a.type), "description": a.description} for a in simulation.agents]
        events_data = [{"round": e.round, "description": e.description} for e in simulation.events[-10:]]

        generated = await self.llm.generate_intervention_options(
            simulation_name=simulation.name,
            simulation_description=simulation.description,
            agents=agents_data,
            recent_events=events_data,
            current_round=simulation.current_round,
        )

        if not generated.event_options and not generated.agent_options and not generated.env_options:
            raise LLMError("干预建议生成失败，请稍后重试或手动输入")

        logger.info("[InterventionService] generate_options 完成 (global)")
        return {
            "event_options": _to_options(generated.event_options),
            "env_options": _to_options(generated.env_options),
            "option_type": "global",
            "generated": True,
        }
