"""内存版 Simulation Repository。

所有推演状态保存在进程内存中，重启后丢失。
后续可无缝替换为 Redis / PostgreSQL 实现。
"""

import logging
from typing import Optional

from core.domain.simulation import Simulation
from .base import SimulationRepository

logger = logging.getLogger(__name__)


class InMemorySimulationRepository(SimulationRepository):
    """内存推演存储"""

    def __init__(self) -> None:
        self._store: dict[str, Simulation] = {}
        logger.info("[InMemorySimulationRepository] 初始化完成")

    async def save(self, simulation: Simulation) -> None:
        sim_id = simulation.id
        self._store[sim_id] = simulation
        logger.debug("[Repository] save simulation=%s, total=%d", sim_id, len(self._store))

    async def get(self, simulation_id: str) -> Optional[Simulation]:
        sim = self._store.get(simulation_id)
        if sim:
            logger.debug("[Repository] get simulation=%s 命中", simulation_id)
        else:
            logger.debug("[Repository] get simulation=%s 未命中", simulation_id)
        return sim

    async def delete(self, simulation_id: str) -> bool:
        if simulation_id in self._store:
            del self._store[simulation_id]
            logger.info("[Repository] delete simulation=%s 成功", simulation_id)
            return True
        logger.warning("[Repository] delete simulation=%s 不存在", simulation_id)
        return False

    async def list_all(self) -> list[Simulation]:
        sims = list(self._store.values())
        logger.debug("[Repository] list_all count=%d", len(sims))
        return sims

    async def list_by_status(self, status: str) -> list[Simulation]:
        sims = [s for s in self._store.values() if s.status.value == status]
        logger.debug("[Repository] list_by_status status=%s count=%d", status, len(sims))
        return sims
