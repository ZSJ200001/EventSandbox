"""推演业务服务。

封装 SimulationEngine 的底层操作，为 Router 提供高内聚的用例接口。
"""

import logging
from datetime import datetime
from typing import Optional

from core.domain.simulation import Simulation, SimulationConfig
from core.domain.common import SimulationStatus
from core.exceptions import SimulationNotFoundError, SimulationPausedError, ValidationError
from engines.simulation_engine import SimulationEngine

logger = logging.getLogger(__name__)


class SimulationService:
    """推演业务服务"""

    def __init__(self, engine: SimulationEngine):
        self.engine = engine
        logger.info("[SimulationService] 初始化完成")

    async def create(
        self,
        name: str,
        description: str,
        event_text: str,
        config: Optional[SimulationConfig] = None,
        rounds: int = 10,
    ) -> Simulation:
        """创建推演"""
        logger.info("[SimulationService] create 开始, name=%s", name)
        if not name or not name.strip():
            raise ValidationError("推演名称不能为空")
        if not event_text or not event_text.strip():
            raise ValidationError("事件描述不能为空")
        if rounds < 1 or rounds > 100:
            raise ValidationError("回合数必须在 1-100 之间")

        # 时间切片配置：解析前端传入的 ISO 时间字符串
        if config and config.start_datetime and isinstance(config.start_datetime, str):
            try:
                config.start_datetime = datetime.fromisoformat(config.start_datetime.replace('Z', '+00:00'))
            except Exception:
                logger.warning("[SimulationService] start_datetime 解析失败，使用当前时间")
                config.start_datetime = datetime.now()

        simulation = await self.engine.create_simulation(
            name=name.strip(),
            description=description or "",
            event_text=event_text.strip(),
            config=config,
            rounds=rounds,
        )
        logger.info("[SimulationService] create 完成, id=%s", simulation.id)
        return simulation

    async def get(self, simulation_id: str) -> Simulation:
        """获取推演"""
        logger.info("[SimulationService] get 开始, id=%s", simulation_id)
        simulation = await self.engine.get_simulation(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)
        return simulation

    def is_stepping(self, simulation_id: str) -> bool:
        """判断推演当前是否正在执行 step"""
        return self.engine.is_stepping(simulation_id)

    async def step(
        self,
        simulation_id: str,
    ) -> dict:
        """执行一回合"""
        logger.info("[SimulationService] step 开始, id=%s", simulation_id)
        simulation, new_events, updated_agents, action_results = await self.engine.step(
            simulation_id=simulation_id,
        )

        round_summary = f"第 {simulation.current_round} 回合完成"
        if new_events:
            round_summary += f"，产生 {len(new_events)} 个事件"

        logger.info("[SimulationService] step 完成, id=%s, round=%d", simulation_id, simulation.current_round)
        return {
            "simulation": simulation,
            "new_events": new_events,
            "updated_agents": updated_agents,
            "action_results": action_results,
            "round_summary": round_summary,
        }

    async def batch_step(
        self,
        simulation_id: str,
        steps: int = 5,
        stop_on_condition: Optional[str] = None,
        conflict_threshold: float = 0.8,
    ) -> dict:
        """批量执行多回合（原子操作：任一回合失败则整体回滚）"""
        logger.info("[SimulationService] batch_step 开始, id=%s, steps=%d", simulation_id, steps)

        # 批量开始前保存完整快照，用于失败时整体回滚
        snapshot = await self.get(simulation_id)
        snapshot_data = snapshot.model_dump(mode="json")

        executed = 0
        all_events = []
        stop_reason = "completed"

        for i in range(steps):
            try:
                result = await self.step(simulation_id)
                executed += 1
                all_events.extend(result["new_events"])
                simulation = result["simulation"]

                if simulation.status == SimulationStatus.COMPLETED:
                    stop_reason = "completed"
                    break

                if stop_on_condition == "conflict_threshold" and simulation.metrics.conflict_level >= conflict_threshold:
                    stop_reason = f"conflict_threshold_reached ({simulation.metrics.conflict_level:.2f})"
                    break

            except SimulationPausedError:
                logger.info("[SimulationService] batch_step 因暂停而终止于第 %d 回合", i + 1)
                stop_reason = "paused"
                break
            except Exception as e:
                logger.error("[SimulationService] batch_step 第 %d 回合异常: %s", i + 1, e, exc_info=True)
                # 回滚到批量开始前的状态
                try:
                    restored = Simulation.model_validate(snapshot_data)
                    await self.engine.repo.save(restored)
                    logger.info("[SimulationService] batch_step 已回滚到第 %d 回合前状态", i + 1)
                except Exception as rollback_err:
                    logger.error("[SimulationService] batch_step 回滚失败: %s", rollback_err, exc_info=True)
                raise

        simulation = await self.get(simulation_id)
        logger.info(
            "[SimulationService] batch_step 完成, id=%s, executed=%d, stop_reason=%s",
            simulation_id, executed, stop_reason,
        )
        return {
            "simulation": simulation,
            "steps_executed": executed,
            "events_generated": all_events,
            "final_metrics": simulation.metrics,
            "stop_reason": stop_reason,
        }

    async def delete(self, simulation_id: str) -> bool:
        """删除推演"""
        logger.info("[SimulationService] delete 开始, id=%s", simulation_id)
        result = await self.engine.delete_simulation(simulation_id)
        logger.info("[SimulationService] delete 完成, id=%s, result=%s", simulation_id, result)
        return result

    async def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """列出推演"""
        logger.info("[SimulationService] list_all 开始, status=%s, limit=%d, offset=%d", status, limit, offset)
        simulations = await self.engine.list_simulations(status=status)
        total = len(simulations)
        paginated = simulations[offset:offset + limit]
        logger.info("[SimulationService] list_all 完成, total=%d", total)
        return {"simulations": paginated, "total": total, "limit": limit, "offset": offset}

    async def pause(self, simulation_id: str) -> Simulation:
        logger.info("[SimulationService] pause 开始, id=%s", simulation_id)
        return await self.engine.pause_simulation(simulation_id)

    async def resume(self, simulation_id: str) -> Simulation:
        logger.info("[SimulationService] resume 开始, id=%s", simulation_id)
        return await self.engine.resume_simulation(simulation_id)
