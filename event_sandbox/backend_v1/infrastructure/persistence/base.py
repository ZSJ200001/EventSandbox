"""持久化抽象接口（Repository 模式）。

定义 Simulation 的存储、查询、删除契约，便于后续替换为 Redis / PostgreSQL 实现。
"""

from abc import ABC, abstractmethod
from typing import Optional

from core.domain.simulation import Simulation


class SimulationRepository(ABC):
    """推演 Repository 抽象基类"""

    @abstractmethod
    async def save(self, simulation: Simulation) -> None:
        """保存或更新推演"""
        ...

    @abstractmethod
    async def get(self, simulation_id: str) -> Optional[Simulation]:
        """根据 ID 获取推演"""
        ...

    @abstractmethod
    async def delete(self, simulation_id: str) -> bool:
        """删除推演，返回是否成功"""
        ...

    @abstractmethod
    async def list_all(self) -> list[Simulation]:
        """列出所有推演"""
        ...

    @abstractmethod
    async def list_by_status(self, status: str) -> list[Simulation]:
        """按状态过滤推演"""
        ...
