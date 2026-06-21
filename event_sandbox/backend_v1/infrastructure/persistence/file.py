"""文件版 Simulation Repository（按需加载优化版）。

解决内存膨胀问题：
- 内存中只保留推演摘要（id/name/status/round 等轻量信息），用于列表查询
- 完整推演数据（实体、事件、关系、拓扑等）保存在磁盘 JSON 文件中
- 调用 get() 时才从磁盘实时加载完整对象
- save() 时写磁盘 + 更新内存摘要
- 前端列表页展示轻量信息，进入具体推演或新建时才加载完整数据
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

from core.domain.simulation import Simulation
from .base import SimulationRepository

logger = logging.getLogger(__name__)

# 默认数据目录：backend_v1/data/simulations/
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "simulations"


class _SimSummary:
    """内存中保留的推演摘要（极轻量）"""

    __slots__ = ("id", "name", "description", "status", "current_round", "rounds", "agent_count", "event_count", "created_at")

    def __init__(self, simulation: Simulation) -> None:
        self.id: str = simulation.id
        self.name: str = simulation.name
        self.description: str = simulation.description
        self.status = simulation.status
        self.current_round: int = simulation.current_round
        self.rounds: int = simulation.rounds
        self.agent_count: int = len(simulation.agents)
        self.event_count: int = len(simulation.events)
        self.created_at: int = getattr(simulation, "start_time", None) or int(time.time() * 1000)

    def to_simulation_stub(self) -> Simulation:
        """生成一个只有基础字段的 Simulation 占位对象，用于列表接口"""
        return Simulation(
            id=self.id,
            name=self.name,
            description=self.description,
            status=self.status,
            current_round=self.current_round,
            rounds=self.rounds,
            agent_count=self.agent_count,
            event_count=self.event_count,
            start_time=self.created_at,
        )


class FileBasedSimulationRepository(SimulationRepository):
    """基于 JSON 文件的推演持久化存储（按需加载）"""

    def __init__(self, data_dir: Optional[Path | str] = None) -> None:
        # 内存中只存摘要
        self._summaries: dict[str, _SimSummary] = {}
        self._data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._scan_summaries()
        logger.info(
            "[FileBasedRepository] 初始化完成, data_dir=%s, 内存摘要=%d",
            self._data_dir,
            len(self._summaries),
        )

    # ---------- 文件 IO ----------

    def _file_path(self, simulation_id: str) -> Path:
        return self._data_dir / f"{simulation_id}.json"

    def _save_to_file(self, simulation: Simulation) -> None:
        """将推演完整数据写入 JSON 文件"""
        file_path = self._file_path(simulation.id)
        try:
            data = simulation.model_dump(mode="json", by_alias=False)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("[FileBasedRepository] 已写入文件 %s", file_path.name)
        except Exception:
            logger.exception("[FileBasedRepository] 写入文件失败 %s", file_path.name)

    def _load_from_file(self, simulation_id: str) -> Optional[Simulation]:
        """从 JSON 文件加载完整推演数据"""
        file_path = self._file_path(simulation_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            simulation = Simulation.model_validate(data)
            logger.debug("[FileBasedRepository] 从磁盘加载推演 %s (%s)", simulation_id, simulation.name)
            return simulation
        except Exception:
            logger.exception("[FileBasedRepository] 加载文件失败 %s", file_path.name)
            return None

    def _delete_file(self, simulation_id: str) -> None:
        file_path = self._file_path(simulation_id)
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info("[FileBasedRepository] 已删除文件 %s", file_path.name)
        except Exception:
            logger.exception("[FileBasedRepository] 删除文件失败 %s", file_path.name)

    def _scan_summaries(self) -> None:
        """启动时扫描目录，仅将摘要加载到内存"""
        if not self._data_dir.exists():
            return

        loaded = 0
        failed = 0
        for file_path in self._data_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 只提取摘要字段，不实例化完整的 Simulation（避免加载 agents/events/relations 等大对象）
                summary = _SimSummary(
                    Simulation.model_validate(data)
                )
                self._summaries[summary.id] = summary
                loaded += 1
            except Exception:
                logger.exception("[FileBasedRepository] 扫描文件失败 %s, 将跳过", file_path.name)
                failed += 1

        if loaded or failed:
            logger.info("[FileBasedRepository] 启动扫描完成: 成功 %d, 失败 %d", loaded, failed)

    # ---------- Repository 接口 ----------

    async def save(self, simulation: Simulation) -> None:
        sim_id = simulation.id
        # 同步计数字段，确保 JSON 中保存正确的数量
        simulation.agent_count = len(simulation.agents)
        simulation.event_count = len(simulation.events)
        # 更新内存摘要
        self._summaries[sim_id] = _SimSummary(simulation)
        # 异步写完整数据到磁盘
        await asyncio.to_thread(self._save_to_file, simulation)
        logger.debug("[FileBasedRepository] save simulation=%s, 内存摘要数=%d", sim_id, len(self._summaries))

    async def get(self, simulation_id: str) -> Optional[Simulation]:
        """按需从磁盘加载完整推演数据"""
        summary = self._summaries.get(simulation_id)
        if not summary:
            logger.debug("[FileBasedRepository] get simulation=%s 未找到摘要", simulation_id)
            return None

        simulation = await asyncio.to_thread(self._load_from_file, simulation_id)
        if simulation:
            logger.debug("[FileBasedRepository] get simulation=%s 从磁盘加载成功", simulation_id)
        else:
            logger.warning("[FileBasedRepository] get simulation=%s 摘要存在但文件缺失", simulation_id)
        return simulation

    async def delete(self, simulation_id: str) -> bool:
        if simulation_id in self._summaries:
            del self._summaries[simulation_id]
            await asyncio.to_thread(self._delete_file, simulation_id)
            logger.info("[FileBasedRepository] delete simulation=%s 成功", simulation_id)
            return True
        logger.warning("[FileBasedRepository] delete simulation=%s 不存在", simulation_id)
        return False

    async def list_all(self) -> list[Simulation]:
        """返回所有推演的基础占位对象（仅含摘要字段）"""
        stubs = [s.to_simulation_stub() for s in self._summaries.values()]
        logger.debug("[FileBasedRepository] list_all count=%d", len(stubs))
        return stubs

    async def list_by_status(self, status: str) -> list[Simulation]:
        """按状态过滤，返回占位对象"""
        stubs = [s.to_simulation_stub() for s in self._summaries.values() if s.status.value == status]
        logger.debug("[FileBasedRepository] list_by_status status=%s count=%d", status, len(stubs))
        return stubs
