"""Agent 决策引擎（精简版）

去掉 personality_traits、deep_profile、beliefs、resources 等冗余字段的依赖，
sentiment 直接读写 agent.sentiment。
"""

import random
import logging
from typing import Optional

from core.domain.common import AgentType
from core.domain.agent import Agent, MemoryEntry
from core.domain.event import Event
from core.domain.relation import RelationEdge
from core.domain.simulation import Simulation, TimelineEntry
from infrastructure.llm.client import AsyncLLMClient
from infrastructure.llm.schemas import AgentDecisionOutput

logger = logging.getLogger(__name__)


class AgentEngine:
    """Agent 决策引擎"""

    def __init__(self, llm_client: AsyncLLMClient):
        self.llm = llm_client
        logger.info("[AgentEngine] 初始化完成")

    def build_situation_summary(self, agent: Agent, current_round: int, main_line_pressure: str = "") -> str:
        """构建局势摘要"""
        agent_type_str = agent.type.value if hasattr(agent.type, "value") else str(agent.type)
        lines = [f"你是 {agent.name}（{agent_type_str}）"]

        # 直接读取 sentiment 字段
        if agent.sentiment != 0:
            label = "积极" if agent.sentiment > 0.3 else "消极" if agent.sentiment < -0.3 else "中性"
            lines.append(f"当前情绪：{label}（{agent.sentiment:.2f}）")

        # 动态属性（简短展示前3个）
        if agent.attributes:
            attrs = list(agent.attributes.items())[:3]
            lines.append("属性：" + ", ".join([f"{k}={v}" for k, v in attrs]))

        # 记忆上下文
        if agent.memory.short_term:
            recent = agent.memory.get_recent_context(limit=3)
            if recent:
                lines.append(f"\n最近记忆：\n{recent}")

        # 主线压力提示
        if main_line_pressure:
            lines.append(f"\n{main_line_pressure}")

        return "\n".join(lines)

    def build_relationships_context(self, agent: Agent, all_agents: list[Agent], relations: list[RelationEdge]) -> str:
        """构建关系上下文（只包含当前Agent作为source的关系）"""
        outgoing = [r for r in relations if r.source_id == agent.id]
        if not outgoing:
            return "暂无明确关系"

        lines = []
        for rel in outgoing:
            target = next((a for a in all_agents if a.id == rel.target_id), None)
            if target:
                lines.append(f"- {target.name}：{rel.relation}（{rel.description}）")

        return "\n".join(lines) if lines else "暂无关系"

    def build_visible_actions_context(self, agent: Agent, all_agents: list[Agent], timeline: list[dict]) -> str:
        """构建可见行动上下文（从 timeline 中筛选 agent_action 类型）"""
        actions = [e for e in timeline if e.get("type") == "agent_action"]
        if not actions:
            return "暂无新的行动信息"

        visible = []
        for action in actions:
            targets = action.get("details", {}).get("target_agents", [])
            if not targets:
                visible.append(action)
                continue
            if agent.name in targets or agent.name == action.get("actor"):
                visible.append(action)
                continue
            if random.random() < 0.1:
                leaked = dict(action)
                leaked["description"] = f"【传闻】{leaked.get('description', '')}"
                visible.append(leaked)

        if not visible:
            return "暂无你收到的新的行动信息"

        lines = []
        for a in visible[-8:]:
            sender = a.get("actor", "未知")
            desc = a.get("description", "")
            action_name = a.get("action", "")
            targets = a.get("details", {}).get("target_agents", [])
            target_str = f"（针对 {', '.join(targets)}）" if targets else "（公开行动）"
            lines.append(f"- {sender} {action_name}{target_str}：{desc}")

        return "\n".join(lines)

    def build_environment_context(self, environment_state: dict) -> str:
        if not environment_state:
            return ""
        lines = ["\n【环境状态】"]
        for k, v in environment_state.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    async def decide_action(
        self,
        agent: Agent,
        all_agents: list[Agent],
        recent_events: list[Event],
        current_round: int,
        knowledge_context: str = "",
        relations: Optional[list[RelationEdge]] = None,
        timeline: Optional[list[dict]] = None,
        environment_state: Optional[dict] = None,
        main_line_pressure: str = "",
        time_context: Optional[dict] = None,
        event_types: Optional[list[str]] = None,
    ) -> AgentDecisionOutput:
        """决定 Agent 在当前回合的行动。LLM 失败时返回默认观望行为。"""
        logger.info("[AgentEngine] decide_action 开始, agent=%s, round=%d", agent.name, current_round)

        try:
            situation = self.build_situation_summary(agent, current_round, main_line_pressure)
            situation += "\n\n【关系网络】\n" + self.build_relationships_context(agent, all_agents, relations or [])

            agent_actions = [e for e in (timeline or []) if e.get("type") == "agent_action"]
            visible_actions = [a for a in agent_actions if a.get("round", 0) < current_round]
            situation += "\n\n【近期收到的信息】\n" + self.build_visible_actions_context(agent, all_agents, visible_actions)

            env_ctx = self.build_environment_context(environment_state or {})
            if env_ctx:
                situation += env_ctx


            recent_history = agent.memory.get_recent_context(limit=3)

            # 提取本 Agent 过去3回合的行动，用于提示词中的多样性约束
            recent_own_actions = [
                e for e in agent.event_log
                if e.get("type") == "action"
                and e.get("round", 0) >= current_round - 3
                and e.get("round", 0) < current_round
            ][-3:]
            own_action_summary = ""
            if recent_own_actions:
                lines = [f"- 回合{a.get('round', '?')}: {a.get('action', '行动')}" for a in recent_own_actions]
                own_action_summary = "\n【你过去几回合的行动】\n" + "\n".join(lines)

            is_forced_response = False
            prev_round_actions = [a for a in agent_actions if a.get("round", 0) == current_round - 1]
            for a in prev_round_actions:
                if agent.name in a.get("details", {}).get("target_agents", []):
                    is_forced_response = True
                    break

            relationships_data = []
            if relations:
                for rel in relations:
                    if rel.source_id != agent.id:
                        continue
                    target = next((a for a in all_agents if a.id == rel.target_id), None)
                    if target:
                        relationships_data.append({
                            "relation_id": rel.id,
                            "source_id": rel.source_id,
                            "source_name": agent.name,
                            "target_id": rel.target_id,
                            "target_name": target.name,
                            "relation": rel.relation,
                            "description": rel.description,
                        })

            decision = await self.llm.decide_action(
                agent_name=agent.name,
                agent_type=agent.type.value if hasattr(agent.type, "value") else str(agent.type),
                agent_personality=agent.personality,
                agent_description=agent.description or f"{agent.name}，{agent.type.value if hasattr(agent.type, 'value') else str(agent.type)}类型角色",
                agent_goals=agent.goals,
                current_situation=situation,
                visible_actions=visible_actions,
                environment_state=environment_state or {},
                knowledge_context=knowledge_context,
                recent_history=recent_history + own_action_summary,
                relationships=relationships_data,
                is_forced_response=is_forced_response,
                all_agents=[{"id": a.id, "name": a.name, "type": a.type.value if hasattr(a.type, "value") else str(a.type)} for a in all_agents],
                time_context=time_context if time_context is not None else None,
                event_types=event_types or [],
            )

            if not decision.action or not decision.action.strip():
                logger.warning("[AgentEngine] LLM 返回空 action, fallback 到观望")
                decision.action = "观望/不行动"

            if decision.action == "观望/不行动":
                logger.info("[AgentEngine] decide_action 完成, agent=%s, action=观望", agent.name)
                return decision

            if not decision.action_description:
                try:
                    decision.action_description = await self.llm.generate_action_description(
                        agent_name=agent.name,
                        action=decision.action,
                        context=f"第 {current_round} 回合 | {agent.name} 采取行动",
                        target_agents=decision.target_agents,
                    )
                except Exception as e:
                    logger.warning("[AgentEngine] 生成 action_description 失败: %s, 使用兜底", e)
                    decision.action_description = f"{agent.name} 采取了 {decision.action} 行动。"

            logger.info("[AgentEngine] decide_action 完成, agent=%s, action=%s", agent.name, decision.action)
            return decision

        except Exception as e:
            logger.error("[AgentEngine] decide_action 异常, agent=%s, error=%s", agent.name, e, exc_info=True)
            return AgentDecisionOutput(
                action="观望/不行动",
                reasoning=f"决策过程出现异常，选择观望。异常信息：{e}",
                expected_outcome="维持现状，等待系统恢复",
                sentiment_change=0,
                target_agents=[],
                action_description=f"{agent.name} 因系统原因选择观望。",
            )

    def apply_action_result(
        self,
        agent: Agent,
        result: AgentDecisionOutput,
        simulation: Simulation,
        current_round: int,
    ) -> list[tuple[Agent, float]]:
        """应用行动结果到 simulation 和 agent，返回情绪更新列表"""
        logger.info("[AgentEngine] apply_action_result 开始, agent=%s, action=%s", agent.name, result.action)

        all_agents = simulation.agents
        agent.last_action_round = current_round
        agent.action_count += 1

        memory_content = f"{agent.name} {result.action}"
        if result.action_description:
            memory_content += f"：{result.action_description}"
        agent.memory.add_entry(MemoryEntry(
            round=current_round,
            type="action",
            content=memory_content,
            emotional_valence=result.sentiment_change,
            importance=0.7,
        ))

        log_content = result.action_description or result.action
        agent.event_log.append({
            "round": current_round,
            "type": "action",
            "action": result.action,
            "content": log_content,
            "reasoning": result.reasoning,
            "target_agents": result.target_agents,
        })

        def _resolve_agent(id_or_name: str) -> Optional[Agent]:
            """按ID或名称解析Agent"""
            if not id_or_name:
                return None
            resolved = next((a for a in all_agents if a.id == id_or_name), None)
            if not resolved:
                resolved = next((a for a in all_agents if a.name == id_or_name), None)
            return resolved

        # 处理 relation_changes，同时收集 before/after
        relation_changes = []
        for ru in result.relation_changes:
            action = ru.get("action", "")
            relation_id = ru.get("relation_id", "")
            source_id_or_name = ru.get("source_id", "")
            target_id_or_name = ru.get("target_id", "")
            relation_label = ru.get("relation", "")

            # 解析 source，必须等于当前 Agent
            source = _resolve_agent(source_id_or_name) if source_id_or_name else agent
            if not source or source.id != agent.id:
                logger.warning("[AgentEngine] relation_change source_id 不是当前 Agent 或无法解析，跳过: %s", source_id_or_name)
                continue

            # 解析 target
            target = _resolve_agent(target_id_or_name)
            if not target:
                logger.warning("[AgentEngine] relation_change 目标未找到: %s", target_id_or_name)
                continue

            if target.id == source.id:
                logger.debug("[AgentEngine] relation_change 目标不能是自己，跳过")
                continue

            # 查找旧关系：优先 relation_id，其次 (source, target, relation)，最后 (source, target) 最近交互
            rel = None
            if action == "update" and relation_id:
                rel = simulation.get_relation_by_id(relation_id)
                if rel and rel.source_id != source.id:
                    # 不能更新不属于当前 Agent 的关系
                    rel = None

            if not rel and relation_label:
                rel = simulation.find_relation(source.id, target.id, relation_label)

            # fallback：LLM 常常未提供 relation_id，或在关系标签变化时误用 create
            # 若 source→target 已存在任何关系，优先更新最近交互的一条，避免同一对实体之间堆积多条重复关系
            if not rel:
                candidates = [
                    r for r in simulation.relations
                    if r.source_id == source.id and r.target_id == target.id
                ]
                if candidates:
                    rel = max(candidates, key=lambda r: (r.last_interaction_round, r.interaction_count))

            old_relation = ""
            old_polarity = ""

            if rel:
                # 更新已有关系（允许关系标签变化）
                old_relation = rel.relation
                old_polarity = rel.polarity
                rel.evolution_history.append({
                    "round": current_round,
                    "relation": rel.relation,
                    "description": rel.description,
                    "polarity": rel.polarity,
                })
                rel.relation = relation_label
                rel.description = ru.get("description", "")
                rel.polarity = ru.get("polarity", "")
                rel.last_interaction_round = current_round
                rel.interaction_count += 1
            else:
                # 新建关系
                rel = RelationEdge(
                    source_id=source.id,
                    target_id=target.id,
                    relation=relation_label,
                    description=ru.get("description", ""),
                    polarity=ru.get("polarity", ""),
                    created_round=current_round,
                    last_interaction_round=current_round,
                    interaction_count=1,
                )
                rel.evolution_history.append({
                    "round": current_round,
                    "relation": relation_label,
                    "description": ru.get("description", ""),
                    "polarity": ru.get("polarity", ""),
                })
                simulation.relations.append(rel)

            relation_changes.append({
                "relation_id": rel.id,
                "target_name": target.name,
                "before_relation": old_relation,
                "before_polarity": old_polarity,
                "after_relation": rel.relation,
                "after_polarity": rel.polarity,
            })
            logger.debug("[AgentEngine] 关系更新: %s -> %s [%s]", agent.name, target.name, rel.relation)

        # 构造 timeline 条目
        before = None
        after = None
        if relation_changes:
            before = {"relation": relation_changes[0]["before_relation"], "polarity": relation_changes[0]["before_polarity"]}
            after = {"relation": relation_changes[0]["after_relation"], "polarity": relation_changes[0]["after_polarity"]}

        simulation.timeline.append(TimelineEntry(
            round=current_round,
            type="agent_action",
            actor=agent.name,
            action=result.action,
            description=result.action_description or f"{agent.name} 采取了 {result.action} 行动",
            before=before,
            after=after,
            details={
                "reasoning": result.reasoning,
                "sentiment_change": result.sentiment_change,
                "target_agents": result.target_agents,
                "relation_changes": relation_changes,
            },
        ))

        if result.action == "观望/不行动":
            logger.info("[AgentEngine] apply_action_result 完成, agent=%s 观望无更新", agent.name)
            return []

        sentiment_updates: list[tuple[Agent, float]] = []

        # 自身情绪
        self._update_agent_sentiment(agent, result.sentiment_change)
        sentiment_updates.append((agent, result.sentiment_change))

        # 目标情绪
        for target_name in result.target_agents:
            target = next((a for a in all_agents if a.name == target_name), None)
            if target:
                delta = result.sentiment_change * 0.5 * -1
                self._update_agent_sentiment(target, delta)
                sentiment_updates.append((target, delta))

        agent.emotional_intensity = min(1.0, agent.emotional_intensity + abs(result.sentiment_change) * 0.2)

        # 记录本轮行动（不再需要 update_belief，event_log 已覆盖）
        # 如果需要快速查询，可以在 agent 上加一个 last_action 字段，但当前 event_log 已足够

        logger.info("[AgentEngine] apply_action_result 完成, agent=%s, sentiment_updates=%d", agent.name, len(sentiment_updates))
        return sentiment_updates

    def _update_agent_sentiment(self, agent: Agent, sentiment_change: float) -> None:
        """更新 Agent 情绪值 —— 直接读写 agent.sentiment"""
        agent.sentiment = max(-1, min(1, agent.sentiment + sentiment_change))

    def apply_intervention(
        self,
        agent: Agent,
        intervention_type: str,
        parameter: str,
        value,
        current_round: int,
    ) -> dict:
        """应用干预到 Agent"""
        logger.info("[AgentEngine] apply_intervention 开始, agent=%s, type=%s", agent.name, intervention_type)
        results = {"goals_added": [], "sentiment_change": 0}

        if intervention_type == "agent_state":
            if parameter == "sentiment":
                old = agent.sentiment
                agent.sentiment = max(-1, min(1, float(value)))
                results["sentiment_change"] = agent.sentiment - old
            elif parameter == "goal" and isinstance(value, str):
                agent.goals.append(value)
                results["goals_added"].append(value)

        elif intervention_type == "external_event" and isinstance(value, str):
            goal = f"应对外部事件：{value}"
            agent.goals.append(goal)
            results["goals_added"].append(goal)
            sentiment_change = -0.2
            self._update_agent_sentiment(agent, sentiment_change)
            results["sentiment_change"] = sentiment_change

        agent.memory.add_entry(MemoryEntry(
            round=current_round,
            type="intervention",
            content=f"受到外部干预：{parameter} = {value}",
            emotional_valence=results["sentiment_change"],
            importance=0.9,
        ))

        logger.info("[AgentEngine] apply_intervention 完成, agent=%s", agent.name)
        return results
