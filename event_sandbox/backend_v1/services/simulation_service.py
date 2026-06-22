"""推演业务服务。

封装 SimulationEngine 的底层操作，为 Router 提供高内聚的用例接口。
"""

import logging
import time
import uuid
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
        # 批量推演异步任务状态（内存存储，进程重启后丢失）
        self._batch_tasks: dict[str, dict] = {}
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
        """启动批量推演异步任务，立即返回任务信息"""
        logger.info("[SimulationService] batch_step 启动异步任务, id=%s, steps=%d", simulation_id, steps)

        # 校验推演存在且可被操作
        simulation = await self.get(simulation_id)
        if simulation.status == SimulationStatus.COMPLETED:
            raise ValidationError("推演已完成，无法继续批量推进")

        # 同一推演不能同时存在多个进行中的批量任务
        for task in self._batch_tasks.values():
            if task["simulation_id"] == simulation_id and task["status"] in ("pending", "running"):
                raise ValidationError("该推演已有正在执行的批量任务，请等待完成")

        task_id = f"{simulation_id}_{uuid.uuid4().hex[:8]}"
        now = time.time()
        task = {
            "task_id": task_id,
            "simulation_id": simulation_id,
            "status": "pending",
            "steps_requested": steps,
            "steps_executed": 0,
            "events_generated": 0,
            "current_round": simulation.current_round,
            "stop_reason": "",
            "error": "",
            "created_at": now,
            "updated_at": now,
        }
        self._batch_tasks[task_id] = task

        # 启动后台任务，不阻塞 HTTP 响应
        import asyncio
        asyncio.create_task(
            self._run_batch(task_id, simulation_id, steps, stop_on_condition, conflict_threshold)
        )

        return task

    async def _run_batch(
        self,
        task_id: str,
        simulation_id: str,
        steps: int,
        stop_on_condition: Optional[str],
        conflict_threshold: float,
    ) -> None:
        """批量推演实际执行逻辑（后台任务）"""
        task = self._batch_tasks[task_id]
        task["status"] = "running"
        task["updated_at"] = time.time()

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

                # 更新任务进度
                task["steps_executed"] = executed
                task["events_generated"] = len(all_events)
                task["current_round"] = simulation.current_round
                task["updated_at"] = time.time()

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

                task["status"] = "failed"
                task["error"] = f"第 {i + 1} 回合异常: {e}"
                task["updated_at"] = time.time()
                return

        task["status"] = "completed"
        task["stop_reason"] = stop_reason
        task["updated_at"] = time.time()
        logger.info(
            "[SimulationService] batch_step 完成, task_id=%s, executed=%d, stop_reason=%s",
            task_id, executed, stop_reason,
        )

    async def get_batch_status(self, simulation_id: str, task_id: str) -> dict:
        """查询批量推演任务状态"""
        task = self._batch_tasks.get(task_id)
        if not task or task["simulation_id"] != simulation_id:
            raise SimulationNotFoundError(f"批量任务 {task_id}")
        return task

    def _cleanup_old_batch_tasks(self, max_age_seconds: float = 86400) -> None:
        """清理过期的批量任务记录"""
        now = time.time()
        expired = [
            task_id for task_id, task in self._batch_tasks.items()
            if task["status"] in ("completed", "failed") and now - task["updated_at"] > max_age_seconds
        ]
        for task_id in expired:
            del self._batch_tasks[task_id]
        if expired:
            logger.info("[SimulationService] 清理 %d 条过期批量任务记录", len(expired))

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
