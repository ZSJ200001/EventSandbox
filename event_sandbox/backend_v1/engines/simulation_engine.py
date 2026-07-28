"""仿真引擎 - 核心调度器。

核心改进：
- asyncio.Lock 替代 threading.Lock，与 FastAPI 异步模型一致
- 一回合内所有 Agent 决策并行（asyncio.gather）
- 完整日志覆盖
- 容错：单个 Agent 决策失败不影响其他 Agent 继续推演
"""

import asyncio
import logging
import random
import re
import time
import uuid
from typing import Optional

from core.config import get_settings
from core.domain.common import SimulationStatus, EventType, InterventionType, AgentType
from core.domain.agent import Agent
from core.domain.event import Event, EventImpact
from core.domain.relation import RelationEdge
from core.domain.simulation import Simulation, SimulationConfig, SimulationMetrics, Topology, TopologyNode, TopologyEdge, TimelineEntry, RoundSummary, format_simulated_time
from core.exceptions import SimulationNotFoundError, StepLockedError, SimulationCompletedError, SimulationPausedError, EventParseError, ValidationError
from infrastructure.llm.client import AsyncLLMClient
from infrastructure.llm.schemas import EntityExtractionOutput, EntityAttributesOutput, RelationshipExtractionOutput
from infrastructure.persistence.base import SimulationRepository
from engines.agent_engine import AgentEngine

logger = logging.getLogger(__name__)


class SimulationEngine:
    """仿真引擎"""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        repository: SimulationRepository,
    ):
        self.llm = llm_client
        self.repo = repository
        self.agent_engine = AgentEngine(llm_client)
        # 每个 simulation 独立的 asyncio.Lock
        self._step_locks: dict[str, asyncio.Lock] = {}
        logger.info("[SimulationEngine] 初始化完成")

    def _get_lock(self, simulation_id: str) -> asyncio.Lock:
        if simulation_id not in self._step_locks:
            self._step_locks[simulation_id] = asyncio.Lock()
        return self._step_locks[simulation_id]

    def is_stepping(self, simulation_id: str) -> bool:
        """判断指定推演当前是否正在执行 step（锁被占用）"""
        return self._get_lock(simulation_id).locked()

    async def create_simulation(
        self,
        name: str,
        description: str,
        event_text: str,
        config: Optional[SimulationConfig] = None,
        rounds: int = 10,
        progress_callback: Optional[callable] = None,
    ) -> Simulation:
        """创建推演 —— 分四步构建图谱：实体提取 → 属性构建 → 关系提取 → 图谱组装"""
        logger.info("[SimulationEngine] create_simulation 开始, name=%s, text=%s...", name, event_text[:50])

        def _notify(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        config = config or SimulationConfig()
        settings = get_settings()

        _notify("正在提取事件实体...")

        # ========== Step 1: 实体提取（迭代式，最多3轮） ==========
        logger.info("[SimulationEngine] Step 1: 实体提取开始")
        all_entities: list[dict] = []

        try:
            result = await self.llm.extract_entities(event_text)
            all_entities.extend([{"name": e.name, "type": e.type} for e in result.entities])
            logger.info("[SimulationEngine] 初次提取实体: %d 个", len(result.entities))
        except Exception as e:
            logger.error("[SimulationEngine] 实体提取失败: %s", e, exc_info=True)
            raise EventParseError(f"实体提取失败: {e}")

        # 检查遗漏（最多3轮，包括初次）
        for round_idx in range(1, settings.entity_extract_max_rounds):
            try:
                check = await self.llm.check_missing_entities(event_text, all_entities)
                if check.is_complete or not check.entities:
                    logger.info("[SimulationEngine] 实体提取已完整, 轮次=%d", round_idx)
                    break
                new_names = {e.get("name", "") for e in all_entities}
                added = 0
                for e in check.entities:
                    if e.get("name", "") and e.get("name") not in new_names:
                        all_entities.append({"name": e.get("name", ""), "type": e.get("type", "entity")})
                        added += 1
                logger.info("[SimulationEngine] 第%d轮补充实体: %d 个", round_idx + 1, added)
                if added == 0:
                    break
            except Exception as e:
                logger.warning("[SimulationEngine] 遗漏检查失败, 轮次=%d: %s", round_idx, e)
                break

        if not all_entities:
            logger.error("[SimulationEngine] 未提取到任何实体")
            raise EventParseError("未提取到任何实体，无法创建推演")

        logger.info("[SimulationEngine] 实体提取完成, 总计=%d", len(all_entities))
        _notify(f"已提取 {len(all_entities)} 个实体: {', '.join(e['name'] for e in all_entities)}")

        # ========== Step 2: 实体属性构建（并发，受 Semaphore 限制） ==========
        logger.info("[SimulationEngine] Step 2: 实体属性构建开始, 并发上限=%d", settings.entity_build_concurrency)
        _notify(f"正在构建实体属性 (0/{len(all_entities)})...")
        semaphore = asyncio.Semaphore(settings.entity_build_concurrency)

        async def _build_one(entity_info: dict) -> Optional[Agent]:
            async with semaphore:
                name = entity_info.get("name", "未知")
                raw_type = entity_info.get("type", "entity")
                try:
                    # 类型 fallback：如果LLM返回的类型不在枚举中，使用 ENTITY
                    try:
                        agent_type = AgentType(raw_type)
                    except ValueError:
                        logger.warning("[SimulationEngine] 未知实体类型 '%s', fallback 到 entity", raw_type)
                        agent_type = AgentType.ENTITY

                    attrs = await self.llm.build_entity_attributes(name, raw_type, event_text)

                    agent = Agent(
                        name=name,
                        type=agent_type,
                        description=attrs.description,
                        attributes=attrs.attributes,
                        keywords=attrs.keywords,
                        is_actionable=attrs.is_actionable,
                        created_round=0,
                    )

                    # 若不可行动且有控制者，尝试绑定 controller_id
                    if not attrs.is_actionable and attrs.controller:
                        # controller_id 在后续统一解析（此时其他实体可能还未创建）
                        agent.controller_id = attrs.controller  # 暂存名称，后续解析为ID

                    # 可行动实体才生成 personality 和 goals
                    if attrs.is_actionable:
                        try:
                            personality_data = await self.llm.generate_agent_personality(
                                agent_type=raw_type, context=event_text, name=name, existing_agents=[]
                            )
                            personality_raw = personality_data.get("personality", "")
                            if isinstance(personality_raw, list):
                                personality_raw = "、".join(str(p) for p in personality_raw)
                            agent.personality = personality_raw
                            agent.goals = personality_data.get("goals", ["生存", "发展"])
                        except Exception as e:
                            logger.warning("[SimulationEngine] 人格生成失败 %s: %s", name, e)

                    logger.info("[SimulationEngine] Agent 创建成功: %s (%s, actionable=%s)", name, raw_type, attrs.is_actionable)
                    return agent
                except Exception as e:
                    logger.error("[SimulationEngine] Agent 构建失败 %s: %s", name, e, exc_info=True)
                    return None

        agent_results = await asyncio.gather(*[_build_one(ent) for ent in all_entities])
        agents: list[Agent] = [a for a in agent_results if a is not None]

        # 校验：必须至少有一个可行动实体，否则推演无法进行
        actionable_agents = [a for a in agents if a.is_actionable]
        if not actionable_agents:
            logger.error("[SimulationEngine] 未提取到可行动实体, agents=%d", len(agents))
            raise EventParseError("未提取到可行动实体，无法创建推演。请提供更详细的事件描述。")

        # 解析 controller_id（名称 → ID）
        name_to_id = {a.name: a.id for a in agents}
        for agent in agents:
            if agent.controller_id and isinstance(agent.controller_id, str):
                if agent.controller_id in name_to_id:
                    agent.controller_id = name_to_id[agent.controller_id]
                else:
                    # controller 名称不在实体列表中，清空
                    agent.controller_id = None

        logger.info("[SimulationEngine] 实体属性构建完成, agents=%d, actionable=%d", len(agents), len(actionable_agents))
        _notify(f"实体属性构建完成 ({len(agents)} 个, {len(actionable_agents)} 个可行动)")

        # ========== Step 3: 关系提取 ==========
        logger.info("[SimulationEngine] Step 3: 关系提取开始")
        _notify("正在提取实体关系网络...")
        relations: list[RelationEdge] = []
        rel_result = None
        try:
            entities_info = [
                {"name": a.name, "type": str(a.type), "description": a.description}
                for a in agents
            ]
            rel_result = await self.llm.extract_relationships(event_text, entities_info)

            for rel in rel_result.relationships:
                source_name = rel.source
                target_name = rel.target
                source_agent = next((a for a in agents if a.name == source_name), None)
                target_agent = next((a for a in agents if a.name == target_name), None)
                if source_agent and target_agent:
                    new_rel = RelationEdge(
                        source_id=source_agent.id,
                        target_id=target_agent.id,
                        relation=rel.relation,
                        description=rel.description,
                        created_round=0,
                        last_interaction_round=0,
                        interaction_count=1,
                    )
                    new_rel.evolution_history.append({
                        "round": 0,
                        "relation": rel.relation,
                        "description": rel.description,
                        "polarity": "",
                    })
                    relations.append(new_rel)

            logger.info("[SimulationEngine] 关系提取完成, relations=%d", len(relations))
            _notify(f"已提取 {len(relations)} 条关系边")
        except Exception as e:
            logger.error("[SimulationEngine] 关系提取失败: %s", e, exc_info=True)
            # 关系提取失败不阻断推演，继续空关系

        # ========== Step 4: 场景世界模型构建（方案 C）==========
        logger.info("[SimulationEngine] Step 4: 场景世界模型构建开始")
        _notify("正在构建场景世界模型...")
        world_model = None
        try:
            entities_info = [
                {"name": a.name, "type": str(a.type), "description": a.description}
                for a in agents
            ]
            # 构造第 0 回合的时间上下文，供世界模型生成时对齐时间
            time_context = None
            if config.has_time_semantics:
                time_context = {
                    "current_round": 0,
                    "total_rounds": rounds,
                    "current_simulated_time": format_simulated_time(config.get_current_simulated_time(0)),
                    "start_datetime": format_simulated_time(config.start_datetime),
                    "round_duration": config.duration_label,
                    "has_time_semantics": True,
                }
            world_model = await self.llm.extract_world_model(
                event_text=event_text,
                entities_info=entities_info,
                main_line=config.main_line or "",
                time_context=time_context,
            )
            logger.info(
                "[SimulationEngine] 世界模型提取完成, type=%s, state_fields=%d, event_types=%d",
                world_model.scenario_type,
                len(world_model.world_state_schema),
                len(world_model.event_types),
            )
        except Exception as e:
            logger.error("[SimulationEngine] 世界模型提取失败: %s", e, exc_info=True)
            # 失败时使用空模型，推演退化为旧模式
            from infrastructure.llm.schemas import ScenarioWorldModelOutput
            world_model = ScenarioWorldModelOutput()

        # ========== Step 5: 构建图谱 ==========
        logger.info("[SimulationEngine] Step 5: 图谱构建开始")
        _notify("正在组装图谱并保存...")
        initial_event = Event(
            type=EventType.EXTERNAL,
            description=event_text,
            timestamp=int(time.time() * 1000),
            round=0,
            involved_agents=[a.id for a in agents],
        )
        event_relations = rel_result.event_relations if rel_result else []
        topology = self._build_topology(agents, relations, initial_event, event_relations)

        from core.domain.world_model import ScenarioWorldModel

        initial_world_state = dict(world_model.initial_world_state) if world_model else {}

        simulation = Simulation(
            name=name,
            description=description,
            agents=agents,
            events=[initial_event],
            relations=relations,
            topology=topology,
            rounds=rounds,
            current_round=0,
            status=SimulationStatus.PENDING,
            config=config,
            ontology_summary=rel_result.scene_ontology if rel_result else "",
            world_model=ScenarioWorldModel.model_validate(world_model.model_dump()) if world_model else None,
            world_state=initial_world_state,
            metrics=SimulationMetrics(
                cooperation_level=0.5,
                conflict_level=0.3,
                action_diversity=0.0,
            ),
        )
        simulation.snapshot_world_state(0)

        await self.repo.save(simulation)
        logger.info(
            "[SimulationEngine] create_simulation 完成, id=%s, agents=%d, actionable=%d, non_actionable=%d",
            simulation.id,
            len(agents),
            sum(1 for a in agents if a.is_actionable),
            sum(1 for a in agents if not a.is_actionable),
        )
        return simulation

    def _build_topology(
        self,
        agents: list[Agent],
        relations: list[RelationEdge],
        initial_event: Event,
        event_relations: Optional[list[dict]] = None,
    ):
        """构建初始拓扑"""
        topology = Topology(nodes=[], edges=[])

        for agent in agents:
            topology.nodes.append(TopologyNode(
                id=agent.id,
                label=agent.name,
                node_type="agent",
                agent_id=agent.id,
                x=random.uniform(-200, 200),
                y=random.uniform(-200, 200),
                metadata={"agent_type": agent.type},
            ))

        # 事件节点
        event_node_id = f"event_{initial_event.id}"
        topology.nodes.append(TopologyNode(
            id=event_node_id,
            label="初始事件",
            node_type="event",
            x=0,
            y=0,
            metadata={"round": 0, "description": initial_event.description},
        ))

        # 建立 event_relations 查找表（按实体名称）
        event_relation_map = {}
        if event_relations:
            for er in event_relations:
                target = er.target if hasattr(er, 'target') else er.get('target', '')
                if target:
                    event_relation_map[target] = er

        for agent in agents:
            er = event_relation_map.get(agent.name)
            relation = er.relation if er else "影响"
            description = er.description if er else initial_event.description
            # 安全兜底：relation 超过 6 字截断
            if relation and len(relation) > 6:
                relation = relation[:6]
            topology.edges.append(TopologyEdge(
                source=event_node_id,
                target=agent.id,
                edge_type="event_affect",
                relation=relation,
                description=description,
                round=0,
            ))

        for rel in relations:
            topology.edges.append(TopologyEdge(
                source=rel.source_id,
                target=rel.target_id,
                edge_type="agent_relation",
                relation=rel.relation,
                description=rel.description,
                round=0,
            ))

        return topology

    async def step(
        self,
        simulation_id: str,
    ) -> tuple[Simulation, list[Event], list[Agent], list[dict]]:
        """执行一回合推演（不再处理干预，干预通过独立接口即刻生效）"""
        logger.info("[SimulationEngine] step 开始, simulation_id=%s", simulation_id)
        lock = self._get_lock(simulation_id)

        if lock.locked():
            logger.warning("[SimulationEngine] step 被锁定, simulation_id=%s", simulation_id)
            raise StepLockedError(simulation_id)

        async with lock:
            simulation = await self.repo.get(simulation_id)
            if not simulation:
                raise SimulationNotFoundError(simulation_id)

            if simulation.status == SimulationStatus.COMPLETED:
                raise SimulationCompletedError(simulation_id)

            if simulation.status == SimulationStatus.PAUSED:
                raise SimulationPausedError(simulation_id)

            simulation.status = SimulationStatus.RUNNING
            simulation.current_round += 1
            current_round = simulation.current_round
            # 推进后自动同步模拟时间
            simulation.update_simulated_time()
            logger.info("[SimulationEngine] 进入第 %d 回合, simulation_id=%s, simulated_time=%s", current_round, simulation_id, simulation.current_simulated_time.isoformat())

            new_events: list[Event] = []
            action_results: list[dict] = []

            # Agent 决策 —— 只让可行动实体参与，并行执行
            active_agents = [a for a in simulation.get_active_agents() if a.is_actionable]
            non_actionable = [a for a in simulation.get_active_agents() if not a.is_actionable]
            logger.info(
                "[SimulationEngine] 本轮可行动 Agent: %d, 不可行动: %d",
                len(active_agents), len(non_actionable),
            )

            # 如果设置了主线，为关键 Agent 生成主线压力提示
            pressure_map: dict[str, str] = {}
            main_line = simulation.config.main_line if simulation.config else ""
            if main_line and active_agents:
                try:
                    agents_data = [
                        {"name": a.name, "type": str(a.type), "description": a.description}
                        for a in active_agents
                    ]
                    recent_events_data = [
                        {"round": e.round, "description": e.description}
                        for e in simulation.events[-5:]
                    ]
                    pressure_output = await self.llm.generate_main_line_pressure(
                        main_line=main_line,
                        agents=agents_data,
                        recent_events=recent_events_data,
                        current_round=current_round,
                    )
                    pressure_map = pressure_output.pressures or {}
                    logger.info(
                        "[SimulationEngine] 主线压力生成完成, pressures=%d",
                        len(pressure_map),
                    )
                except Exception as e:
                    logger.warning("[SimulationEngine] 主线压力生成失败: %s", e)

            decision_tasks = []
            for agent in active_agents:
                task = self._agent_decide_task(simulation, agent, current_round, pressure_map)
                decision_tasks.append(task)

            # gather 并行执行，return_exceptions=True 保证单个失败不中断整体
            results = await asyncio.gather(*decision_tasks, return_exceptions=True)

            updated_agents: list[Agent] = []
            for agent, result in zip(active_agents, results):
                if isinstance(result, Exception):
                    logger.error("[SimulationEngine] Agent %s 决策异常: %s", agent.name, result, exc_info=True)
                    # 为该 Agent 生成默认观望结果
                    action_results.append({
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "action": "观望/不行动",
                        "reasoning": f"决策异常，选择观望: {result}",
                        "target_agents": [],
                        "action_description": f"{agent.name} 因异常选择观望。",
                        "sentiment_change": 0,
                        "relation_changes": [],
                    })
                    updated_agents.append(agent)
                    continue

                # 应用行动结果
                try:
                    self.agent_engine.apply_action_result(agent, result, simulation, current_round)
                except Exception as e:
                    logger.error("[SimulationEngine] apply_action_result 失败 %s: %s", agent.name, e, exc_info=True)

                action_results.append({
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "action": result.action,
                    "reasoning": result.reasoning,
                    "expected_outcome": result.expected_outcome,
                    "target_agents": result.target_agents,
                    "action_description": result.action_description,
                    "sentiment_change": result.sentiment_change,
                    "relation_changes": result.relation_changes,
                })
                updated_agents.append(agent)

            # 汇总本回合所有 Agent 行动，统一推导世界状态变化
            try:
                round_relation_changes = []
                for entry in simulation.timeline:
                    if entry.round == current_round and entry.type == "agent_action":
                        round_relation_changes.extend(entry.details.get("relation_changes", []))

                world_state_output = await self.llm.aggregate_world_state_updates(
                    current_world_state=simulation.world_state,
                    world_state_schema=simulation.world_model.world_state_schema if simulation.world_model else {},
                    round_actions=action_results,
                    relation_changes=round_relation_changes,
                    current_round=current_round,
                    time_context=simulation.get_time_context(),
                )
                if world_state_output.world_state_updates:
                    simulation.update_world_state(world_state_output.world_state_updates)
                    logger.info("[SimulationEngine] 世界状态更新: %s", world_state_output.world_state_updates)
            except Exception as e:
                logger.error("[SimulationEngine] 世界状态汇总失败: %s", e, exc_info=True)

            # 同步拓扑与指标
            try:
                self._sync_relations_to_topology(simulation)
                self._update_metrics(simulation)
            except Exception as e:
                logger.error("[SimulationEngine] 拓扑/指标同步失败: %s", e, exc_info=True)

            # 记录本回合世界状态快照（方案 C）
            simulation.snapshot_world_state(current_round)

            # 检查终止条件（方案 C：代码执行，LLM 只负责生成世界模型说明）
            if simulation.check_terminal_condition():
                simulation.status = SimulationStatus.COMPLETED
                simulation.end_time = int(time.time() * 1000)
                logger.info("[SimulationEngine] 推演满足终止条件, id=%s, round=%d", simulation_id, current_round)

            # 检查是否结束（基于回合数的兜底）
            if simulation.current_round >= simulation.rounds:
                simulation.status = SimulationStatus.COMPLETED
                simulation.end_time = int(time.time() * 1000)
                logger.info("[SimulationEngine] 推演完成, id=%s", simulation_id)

            # 记录指标历史
            simulation.metrics_history.append({
                "round": current_round,
                **simulation.metrics.to_display_dict(),
            })

            # 生成本回合摘要
            round_summary = self._generate_round_summary(simulation, current_round)
            simulation.round_summaries.append(round_summary)

            await self.repo.save(simulation)
            logger.info(
                "[SimulationEngine] step 完成, simulation_id=%s, round=%d, events=%d, actions=%d, timeline=%d",
                simulation_id, current_round, len(new_events), len(action_results), len(simulation.timeline),
            )
            return simulation, new_events, updated_agents, action_results

    @staticmethod
    def _generate_round_summary(simulation: Simulation, current_round: int) -> RoundSummary:
        """基于本回合 timeline 条目生成回合摘要（纯代码规则，无需 LLM）"""
        entries = [e for e in simulation.timeline if e.round == current_round]
        if not entries:
            return RoundSummary(round=current_round, summary=f"第{current_round}回合：无重要事件。")

        # 重要性分级
        important = []
        for e in entries:
            level = "C"
            if e.type == "external_event":
                level = "S"
            elif e.type == "agent_action":
                details = e.details or {}
                has_polarity_shift = False
                if e.before and e.after:
                    before_p = e.before.get("polarity", "")
                    after_p = e.after.get("polarity", "")
                    if before_p and after_p and before_p != after_p:
                        has_polarity_shift = True
                if has_polarity_shift:
                    level = "S"
                elif details.get("relation_changes"):
                    level = "A"
                elif abs(details.get("sentiment_change", 0)) > 0.3:
                    level = "A"
                elif details.get("target_agents"):
                    level = "A"
                elif e.action != "观望/不行动":
                    level = "B"
            elif e.type == "agent_added":
                level = "A"

            if level in ("S", "A"):
                important.append((level, e))

        # 按重要性排序，截断前 5 条
        important.sort(key=lambda x: ("S", "A").index(x[0]))
        important = important[:5]

        # 模板拼接
        fragments = []
        key_events = []
        for level, e in important:
            if e.type == "external_event":
                fragments.append(f"外部事件：{e.description}")
                key_events.append("外部事件")
            elif e.type == "agent_added":
                fragments.append(f"新增实体「{e.actor}」")
                key_events.append("新增实体")
            elif e.type == "agent_action":
                details = e.details or {}
                targets = details.get("target_agents", [])
                target_str = f"对{'、'.join(targets)}" if targets else ""
                if e.before and e.after:
                    old_r = e.before.get("relation", "")
                    new_r = e.after.get("relation", "")
                    fragments.append(f"{e.actor}{target_str}采取{e.action}（双方关系从「{old_r}」变为「{new_r}」）")
                    key_events.append("关系质变")
                else:
                    fragments.append(f"{e.actor}{target_str}采取{e.action}")
                    if e.action != "观望/不行动":
                        key_events.append("主动行动")

        summary = f"第{current_round}回合：" + "；".join(fragments) if fragments else f"第{current_round}回合：各方主要采取观望姿态。"
        significance = "critical" if any(l == "S" for l, _ in important) else ("important" if important else "normal")
        return RoundSummary(round=current_round, summary=summary, key_events=key_events, significance=significance)

    def _resolve_agent_id(self, simulation: Simulation, name_or_id: str) -> Optional[str]:
        """将 agent 名字或 ID 解析为 UUID"""
        if not name_or_id:
            return None
        # 先按 UUID 匹配
        agent = simulation.get_agent_by_id_or_name(name_or_id)
        if agent:
            return agent.id
        # 再按名字匹配
        agent = next((a for a in simulation.agents if a.name == name_or_id), None)
        if agent:
            return agent.id
        return None

    @staticmethod
    def _extract_impact_relation(log_text: str) -> str:
        """从 agent_log 中解析 【影响类型】 前缀，作为 event_affect 边的 relation"""
        if not log_text:
            return ""
        match = re.search(r"【(.+?)】", log_text)
        if match:
            relation = match.group(1).strip()
            # 安全兜底：超过 6 字截断
            if len(relation) > 6:
                relation = relation[:6]
            return relation
        return ""

    async def inject_event(self, simulation_id: str, description: str) -> Simulation:
        """事件注入 —— 即刻生效，自动发现新实体并分析影响，不推进回合"""
        logger.info("[SimulationEngine] inject_event 开始, simulation_id=%s", simulation_id)
        simulation = await self.repo.get(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)

        current_round = simulation.current_round

        # 1. 提取事件涉及的新实体（LLM 自动发现）
        try:
            extraction = await self.llm.extract_entities(description)
            for entity in extraction.entities:
                name = entity.name
                # 检查是否已存在（按名字）
                existing = next((a for a in simulation.agents if a.name == name), None)
                if not existing:
                    raw_type = entity.type
                    try:
                        agent_type = AgentType(raw_type)
                    except ValueError:
                        agent_type = AgentType.ENTITY

                    llm_attrs = await self.build_agent_attributes(name, raw_type, description)
                    new_agent = Agent(
                        name=name,
                        type=agent_type,
                        description=llm_attrs["description"],
                        attributes=llm_attrs["attributes"],
                        keywords=llm_attrs["keywords"],
                        is_actionable=llm_attrs["is_actionable"],
                        personality=llm_attrs["personality"],
                        goals=llm_attrs["goals"],
                        created_round=current_round,
                    )
                    simulation.agents.append(new_agent)
                    simulation.topology.nodes.append(TopologyNode(
                        id=new_agent.id,
                        label=new_agent.name,
                        node_type="agent",
                        agent_id=new_agent.id,
                        x=random.uniform(-100, 100),
                        y=random.uniform(-100, 100),
                        metadata={"agent_type": new_agent.type},
                    ))
                    logger.info("[SimulationEngine] 事件注入自动创建实体: %s (%s)", name, raw_type)
        except Exception as e:
            logger.warning("[SimulationEngine] 实体提取失败: %s", e)

        # 2. 创建事件
        event = Event(
            type=EventType.EXTERNAL,
            description=description,
            timestamp=int(time.time() * 1000),
            round=current_round,
        )
        simulation.add_event(event)
        logger.info("[SimulationEngine] 创建外部事件, round=%d, desc=%s", current_round, description[:50])

        # 记录外部事件到 timeline
        simulation.timeline.append(TimelineEntry(
            round=current_round,
            type="external_event",
            actor="系统",
            action="事件注入",
            description=description,
            details={"event_id": str(event.id)},
        ))

        # 3. LLM 分析影响（只传入刚创建的这一条事件）
        impact = None
        try:
            impact = await self._analyze_external_impact(simulation, [event], current_round)
        except Exception as e:
            logger.error("[SimulationEngine] 外部影响分析失败: %s", e, exc_info=True)

        # 4. 创建事件拓扑节点
        event_node_id = f"event_{event.id}"
        simulation.topology.nodes.append(TopologyNode(
            id=event_node_id,
            label=description[:20] if len(description) > 20 else description,
            node_type="event",
            x=random.uniform(-100, 100),
            y=random.uniform(-100, 100),
            metadata={"round": current_round, "description": description},
        ))

        # 5. 为受影响的 Agent 创建 event_affect 边
        affected_agent_ids: set[str] = set()
        agent_log_map: dict[str, str] = {}
        if impact:
            for agent_name, log_text in impact.agent_logs.items():
                resolved_id = self._resolve_agent_id(simulation, agent_name)
                if resolved_id:
                    affected_agent_ids.add(resolved_id)
                    agent_log_map[resolved_id] = log_text
            for ru in impact.relation_updates:
                for key in ["source_id", "target_id"]:
                    resolved = self._resolve_agent_id(simulation, ru.get(key, ""))
                    if resolved:
                        affected_agent_ids.add(resolved)

        for agent_id in affected_agent_ids:
            log_text = agent_log_map.get(agent_id, "")
            relation = self._extract_impact_relation(log_text) if log_text else "影响"
            simulation.topology.edges.append(TopologyEdge(
                source=event_node_id,
                target=agent_id,
                edge_type="event_affect",
                relation=relation,
                description=log_text or description,
                round=current_round,
            ))

        # 6. 同步拓扑与指标并保存
        try:
            # 应用外部事件带来的世界状态变化和离散事件（方案 C）
            if impact:
                if impact.world_state_updates:
                    simulation.update_world_state(impact.world_state_updates)
                    simulation.snapshot_world_state(current_round)
                for evt in impact.events:
                    from core.domain.world_model import WorldEvent
                    simulation.add_world_event(WorldEvent(
                        type=evt.get("type", "other"),
                        round=current_round,
                        actor="系统",
                        description=evt.get("description", ""),
                        metadata=evt.get("metadata", {}),
                    ))
                    simulation.timeline.append(TimelineEntry(
                        round=current_round,
                        type="world_event",
                        actor="系统",
                        action=evt.get("type", "other"),
                        description=evt.get("description", ""),
                        details={"event_type": evt.get("type", "other"), "metadata": evt.get("metadata", {})},
                    ))
                # 外部事件可能直接触发终止条件
                if simulation.check_terminal_condition():
                    simulation.status = SimulationStatus.COMPLETED
                    simulation.end_time = int(time.time() * 1000)
                    logger.info("[SimulationEngine] 事件注入后满足终止条件, id=%s", simulation_id)

            self._sync_relations_to_topology(simulation)
            self._update_metrics(simulation)
        except Exception as e:
            logger.error("[SimulationEngine] 拓扑/指标同步失败: %s", e, exc_info=True)

        await self.repo.save(simulation)
        logger.info("[SimulationEngine] inject_event 完成, simulation_id=%s, affected=%d, new_agents=%d",
                     simulation_id, len(affected_agent_ids),
                     sum(1 for a in simulation.agents if a.created_round == current_round))
        return simulation

    async def _agent_decide_task(
        self, simulation: Simulation, agent: Agent, current_round: int, pressure_map: dict[str, str]
    ):
        """单个 Agent 决策任务，用于 asyncio.gather"""
        relations = simulation.get_relations_of(agent.id)
        main_line_pressure = pressure_map.get(agent.name, "")
        return await self.agent_engine.decide_action(
            agent=agent,
            all_agents=simulation.agents,
            recent_events=simulation.events[-10:],
            current_round=current_round,
            knowledge_context="",
            relations=relations,
            timeline=[e.model_dump() for e in simulation.timeline],
            environment_state=simulation.environment_state,
            main_line_pressure=main_line_pressure,
            time_context=simulation.get_time_context(),
            event_types=simulation.world_model.event_types if simulation.world_model else [],
        )

    async def _apply_intervention(
        self, simulation: Simulation, intervention: dict, current_round: int, new_events: list[Event]
    ) -> None:
        """应用干预"""
        intervention_type = intervention.get("type", "")
        target_id = intervention.get("target")
        parameter = intervention.get("parameter", "")
        value = intervention.get("value", "")

        logger.info("[SimulationEngine] 应用干预, type=%s, target=%s", intervention_type, target_id)

        if intervention_type == InterventionType.AGENT_STATE.value and target_id:
            agent = simulation.get_agent_by_id_or_name(target_id)
            if agent:
                self.agent_engine.apply_intervention(agent, "agent_state", parameter, value, current_round)

        elif intervention_type == InterventionType.EXTERNAL_EVENT.value:
            event = Event(
                type=EventType.EXTERNAL,
                description=str(value),
                timestamp=int(time.time() * 1000),
                round=current_round,
                involved_agents=[target_id] if target_id else [],
            )
            simulation.add_event(event)
            new_events.append(event)
            simulation.interventions.append(intervention)

            if target_id:
                agent = simulation.get_agent_by_id_or_name(target_id)
                if agent:
                    self.agent_engine.apply_intervention(agent, "external_event", parameter, value, current_round)

        elif intervention_type == InterventionType.ADD_AGENT.value:
            # 动态添加 Agent（简化实现）
            name = value.get("name", "新加入者") if isinstance(value, dict) else str(value)
            agent_type = value.get("type", "individual") if isinstance(value, dict) else "individual"
            new_agent = Agent(name=name, type=agent_type, description="", created_round=current_round)
            simulation.agents.append(new_agent)
            simulation.topology.nodes.append(TopologyNode(
                id=new_agent.id, label=new_agent.name, node_type="agent", agent_id=new_agent.id,
                x=random.uniform(-100, 100), y=random.uniform(-100, 100),
                metadata={"agent_type": new_agent.type},
            ))
            logger.info("[SimulationEngine] 动态添加 Agent: %s", name)

        elif intervention_type == InterventionType.REMOVE_AGENT.value and target_id:
            agent = simulation.get_agent_by_id_or_name(target_id)
            if agent:
                simulation.agents = [a for a in simulation.agents if a.id != target_id]
                simulation.relations = [r for r in simulation.relations if r.source_id != target_id and r.target_id != target_id]
                simulation.topology.remove_agent_nodes(target_id)
                logger.info("[SimulationEngine] 移除 Agent: %s", agent.name)

    async def _analyze_external_impact(self, simulation: Simulation, external_events: list[Event], current_round: int):
        """分析外部事件影响。返回 ExternalImpactOutput 供调用方进一步处理。"""
        agents_data = [{"id": a.id, "name": a.name, "type": str(a.type), "description": a.description} for a in simulation.agents]
        relations_data = []
        for r in simulation.relations:
            source = simulation.get_agent_by_id_or_name(r.source_id)
            target = simulation.get_agent_by_id_or_name(r.target_id)
            if source and target:
                relations_data.append({
                    "relation_id": r.id,
                    "source_id": r.source_id,
                    "source_name": source.name,
                    "target_id": r.target_id,
                    "target_name": target.name,
                    "relation": r.relation,
                    "description": r.description,
                    "polarity": r.polarity,
                })

        events_data = [{"round": e.round, "type": str(e.type), "description": e.description} for e in external_events]

        impact = await self.llm.analyze_external_impact(
            simulation_name=simulation.name,
            simulation_description=simulation.description,
            agents=agents_data,
            current_relations=relations_data,
            external_events=events_data,
            current_round=current_round,
        )

        logger.info(
            "[SimulationEngine] 外部影响分析原始返回: updates=%d, logs=%s",
            len(impact.relation_updates),
            list(impact.agent_logs.keys()) if impact.agent_logs else "空",
        )

        for ru in impact.relation_updates:
            action = ru.get("action", "")
            relation_id = ru.get("relation_id", "")
            source_id_or_name = ru.get("source_id", "")
            target_id_or_name = ru.get("target_id", "")
            relation_label = ru.get("relation", "")

            source_id = self._resolve_agent_id(simulation, source_id_or_name)
            target_id = self._resolve_agent_id(simulation, target_id_or_name)
            if not source_id or not target_id:
                logger.warning("[SimulationEngine] 外部事件 relation_update 实体解析失败: source=%s, target=%s", source_id_or_name, target_id_or_name)
                continue

            # 查找旧关系
            rel = None
            if action == "update" and relation_id:
                rel = simulation.get_relation_by_id(relation_id)

            if not rel and relation_label:
                rel = simulation.find_relation(source_id, target_id, relation_label)

            if rel:
                # 更新
                rel.evolution_history.append({
                    "round": current_round,
                    "relation": rel.relation,
                    "description": rel.description,
                    "polarity": rel.polarity,
                })
                rel.source_id = source_id
                rel.target_id = target_id
                rel.relation = relation_label
                rel.description = ru.get("description", "")
                rel.polarity = ru.get("polarity", "")
                rel.last_interaction_round = current_round
                rel.interaction_count += 1
            else:
                # 新建
                new_rel = RelationEdge(
                    source_id=source_id,
                    target_id=target_id,
                    relation=relation_label,
                    description=ru.get("description", ""),
                    polarity=ru.get("polarity", ""),
                    created_round=current_round,
                    last_interaction_round=current_round,
                    interaction_count=1,
                )
                new_rel.evolution_history.append({
                    "round": current_round,
                    "relation": relation_label,
                    "description": ru.get("description", ""),
                    "polarity": ru.get("polarity", ""),
                })
                simulation.relations.append(new_rel)

        for agent_id, log in impact.agent_logs.items():
            resolved_id = self._resolve_agent_id(simulation, agent_id)
            agent = simulation.get_agent_by_id_or_name(resolved_id) if resolved_id else None
            if agent:
                agent.event_log.append({"round": current_round, "type": "外部干预", "content": log})

        logger.info("[SimulationEngine] 外部影响分析完成, updates=%d, logs=%d",
                    len(impact.relation_updates), len(impact.agent_logs))
        return impact

    def _sync_relations_to_topology(self, simulation: Simulation) -> None:
        """将全局 relations 同步到拓扑边"""
        # 保留非 agent_relation 边（event_affect 等）
        non_agent_edges = [e for e in simulation.topology.edges if e.edge_type != "agent_relation"]
        simulation.topology.edges = non_agent_edges

        for rel in simulation.relations:
            simulation.topology.edges.append(TopologyEdge(
                source=rel.source_id,
                target=rel.target_id,
                edge_type="agent_relation",
                relation=rel.relation,
                description=rel.description,
                round=rel.created_round,
                interaction_count=rel.interaction_count,
                last_interaction_round=rel.last_interaction_round,
                metadata={"evolution_history": rel.evolution_history},
            ))

    def _update_metrics(self, simulation: Simulation) -> None:
        """重新计算指标"""
        relations = simulation.relations

        # 合作/冲突基于 polarity 字段判定；无 polarity 的视为中立
        cooperation_count = sum(1 for r in relations if r.polarity == "positive")
        conflict_count = sum(1 for r in relations if r.polarity == "negative")
        total = max(1, len(relations))

        simulation.metrics.cooperation_level = round(cooperation_count / total, 2)
        simulation.metrics.conflict_level = round(conflict_count / total, 2)

        # 网络动荡度：本回合发生变更的关系边占比
        changed_relations = sum(
            1 for r in simulation.relations
            if r.last_interaction_round == simulation.current_round
        )
        simulation.metrics.network_turbulence = round(
            changed_relations / max(1, len(simulation.relations)), 2
        )

        # 行动多样性（从 timeline 中筛选 agent_action）
        agent_actions = [e for e in simulation.timeline if e.type == "agent_action"]
        action_counts = {}
        for a in agent_actions:
            action_counts[a.action] = action_counts.get(a.action, 0) + 1
        unique_actions = len(action_counts)
        simulation.metrics.action_diversity = min(1, round(unique_actions / max(1, len(simulation.agents)) * 0.5, 2))

        # 信息熵
        total_actions = len(agent_actions)
        if total_actions > 0:
            import math
            entropy = 0
            for count in action_counts.values():
                p = count / total_actions
                if p > 0:
                    entropy -= p * math.log2(p)
            max_entropy = math.log2(max(2, len(action_counts)))
            simulation.metrics.information_entropy = round(entropy / max_entropy if max_entropy > 0 else 0, 2)

        # 主动权指数
        if agent_actions:
            latest = [a for a in agent_actions if a.round == simulation.current_round]
            active = [a for a in latest if a.action != "观望/不行动"]
            simulation.metrics.initiative_index = round(len(active) / max(1, len(latest)), 2)

    async def build_agent_attributes(self, name: str, agent_type_str: str, context: str) -> dict:
        """为新增实体构建属性（复用创建推演时的 LLM 调用）"""
        logger.info("[SimulationEngine] build_agent_attributes 开始, name=%s, type=%s", name, agent_type_str)

        try:
            attrs = await self.llm.build_entity_attributes(name, agent_type_str, context)
        except Exception as e:
            logger.warning("[SimulationEngine] build_entity_attributes 失败 %s: %s", name, e)
            attrs = None

        description = attrs.description if attrs else ""
        attributes = attrs.attributes if attrs else {}
        keywords = attrs.keywords if attrs else []
        is_actionable = attrs.is_actionable if attrs else True

        personality = ""
        goals = []
        if is_actionable:
            try:
                personality_data = await self.llm.generate_agent_personality(
                    agent_type=agent_type_str, context=context, name=name, existing_agents=[]
                )
                personality_raw = personality_data.get("personality", "")
                if isinstance(personality_raw, list):
                    personality_raw = "、".join(str(p) for p in personality_raw)
                personality = personality_raw
                goals = personality_data.get("goals", ["生存", "发展"])
            except Exception as e:
                logger.warning("[SimulationEngine] 人格生成失败 %s: %s", name, e)

        return {
            "description": description,
            "attributes": attributes,
            "keywords": keywords,
            "is_actionable": is_actionable,
            "personality": personality,
            "goals": goals,
        }

    async def get_simulation(self, simulation_id: str) -> Optional[Simulation]:
        return await self.repo.get(simulation_id)

    async def delete_simulation(self, simulation_id: str) -> bool:
        result = await self.repo.delete(simulation_id)
        if simulation_id in self._step_locks:
            del self._step_locks[simulation_id]
        return result

    async def list_simulations(self, status: Optional[str] = None) -> list[Simulation]:
        if status:
            return await self.repo.list_by_status(status)
        return await self.repo.list_all()

    async def pause_simulation(self, simulation_id: str) -> Simulation:
        simulation = await self.repo.get(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)
        simulation.status = SimulationStatus.PAUSED
        await self.repo.save(simulation)
        logger.info("[SimulationEngine] 推演暂停, id=%s", simulation_id)
        return simulation

    async def resume_simulation(self, simulation_id: str) -> Simulation:
        simulation = await self.repo.get(simulation_id)
        if not simulation:
            raise SimulationNotFoundError(simulation_id)
        simulation.status = SimulationStatus.PENDING if simulation.current_round == 0 else SimulationStatus.RUNNING
        await self.repo.save(simulation)
        logger.info("[SimulationEngine] 推演恢复, id=%s", simulation_id)
        return simulation

    async def get_agent_detail(self, simulation_id: str, agent_id: str) -> Optional[dict]:
        simulation = await self.repo.get(simulation_id)
        if not simulation:
            return None
        agent = simulation.get_agent_by_id_or_name(agent_id)
        if not agent:
            return None

        rels = simulation.get_relations_of(agent_id)
        rel_summary = []
        for r in rels:
            other_id = r.target_id if r.source_id == agent_id else r.source_id
            other = simulation.get_agent_by_id_or_name(other_id)
            if other:
                rel_summary.append({
                    "agent_id": other_id,
                    "agent_name": other.name,
                    "relation": r.relation,
                    "description": r.description,
                    "interaction_count": r.interaction_count,
                })

        visible_actions = [
            a.model_dump() for a in simulation.timeline
            if a.type == "agent_action" and (
                a.actor == agent.name or (
                    not a.details.get("target_agents") or agent.name in a.details.get("target_agents", [])
                )
            )
        ]

        return {
            "agent": agent,
            "recent_memory": agent.memory.get_formatted_memory(),
            "relationship_summary": rel_summary,
            "action_history": agent.event_log[-20:],
            "visible_actions": visible_actions,
        }
