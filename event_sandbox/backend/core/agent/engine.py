import uuid
import time
import random
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.llm import get_llm_client
from models.entities import (
    Agent,
    AgentType,
    AgentStatus,
    Belief,
    Relationship,
    RelationType,
    Event,
    EventType,
    EventImpact,
    MemoryEntry,
    Simulation,
    SimulationConfig,
)


class ActionResult:
    def __init__(
        self,
        action: str,
        reasoning: str,
        expected_outcome: str,
        sentiment_change: float,
        target_agents: list[str],
        event_description: str,
        action_intensity: float = 0.5,
        risk_level: str = "medium",
        cascade_possible: bool = False,
    ):
        self.action = action
        self.reasoning = reasoning
        self.expected_outcome = expected_outcome
        self.sentiment_change = sentiment_change
        self.target_agents = target_agents
        self.event_description = event_description
        self.action_intensity = action_intensity
        self.risk_level = risk_level
        self.cascade_possible = cascade_possible


class AgentEngine:
    """Agent 决策引擎 - 负责 Agent 的决策和行动"""

    # 动作模板
    ACTION_TEMPLATES = {
        AgentType.COMPANY: [
            "调整定价", "推出促销", "扩大产能", "降低成本",
            "建立联盟", "发布声明", "收购竞争者", "研发创新",
            "优化供应链", "开拓市场", "品牌升级"
        ],
        AgentType.COMPETITOR: [
            "匹配降价", "推出竞品", "争夺市场份额", "联盟对抗",
            "攻击声誉", "创新超越", "差异化竞争", "挖角人才"
        ],
        AgentType.CONSUMER: [
            "购买产品", "转换品牌", "投诉反馈", "分享体验",
            "抵制购买", "推荐他人", "等待促销", "比较选择"
        ],
        AgentType.GOVERNMENT: [
            "发布法规", "启动调查", "施加处罚", "宣布政策",
            "召开新闻发布会", "约谈企业", "调整税率"
        ],
        AgentType.REGULATOR: [
            "立案调查", "发出警告", "处以罚款", "宣布政策",
            "举行听证会", "要求整改", "吊销执照"
        ],
        AgentType.SUPPLIER: [
            "调整价格", "修改合同", "扩大产能", "限制供货",
            "优先供货", "拖欠账款", "寻找新客户"
        ],
        AgentType.ORGANIZATION: [
            "发表声明", "组织抗议", "谈判协商", "游说政府",
            "动员成员", "寻求联盟", "舆论施压"
        ],
        AgentType.INDIVIDUAL: [
            "表达观点", "采取行动", "分享信息", "改变行为",
            "寻求帮助", "投诉举报"
        ],
    }

    # 关系强度变化映射
    RELATION_SENTIMENT_IMPACT = {
        RelationType.COMPETITOR: {"self": 0.1, "target": -0.2},
        RelationType.COOPERATIVE: {"self": 0.15, "target": 0.15},
        RelationType.SUPPLY: {"self": -0.05, "target": 0.1},
        RelationType.DEMAND: {"self": 0.1, "target": -0.05},
        RelationType.REGULATE: {"self": -0.15, "target": -0.2},
        RelationType.INFLUENCE: {"self": 0.05, "target": 0.05},
        RelationType.NEUTRAL: {"self": 0, "target": 0},
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client or get_llm_client()

    def get_available_actions(self, agent: Agent) -> list[str]:
        """获取 Agent 可用的动作列表"""
        base_actions = self.ACTION_TEMPLATES.get(agent.type, ["观望", "等待"])

        # 根据状态过滤
        if agent.status == AgentStatus.INACTIVE:
            return ["观望"]
        if agent.status == AgentStatus.INTERVENED:
            # 被干预过的 agent 更谨慎
            base_actions = ["观望", "评估"] + base_actions[:3]

        # 根据性格调整
        if agent.personality_traits.neuroticism > 0.7:
            # 高神经质 - 添加防御性动作
            base_actions = base_actions + ["防御", "保守策略"]

        return base_actions

    def build_situation_summary(
        self,
        agent: Agent,
        all_agents: list[Agent],
        recent_events: list[Event],
        current_round: int = 0
    ) -> str:
        """构建当前情况摘要"""
        lines = [f"你是 {agent.name}，角色：{agent.type.value}"]

        # 角色描述
        if agent.description:
            lines.append(f"角色描述：{agent.description}")

        # 性格特征
        if agent.personality:
            lines.append(f"性格特征：{agent.personality}")
        if agent.personality_traits:
            lines.append(f"性格分析：{agent.personality_traits.to_prompt_string()}")

        # 目标
        if agent.goals:
            lines.append(f"当前目标：{', '.join(agent.goals)}")

        # 当前策略
        if agent.current_strategy:
            lines.append(f"当前策略：{agent.current_strategy}")

        # 情绪状态
        sentiment_belief = agent.get_belief("sentiment")
        if sentiment_belief:
            sentiment = float(sentiment_belief.value)
            sentiment_label = "积极" if sentiment > 0.3 else "消极" if sentiment < -0.3 else "中性"
            lines.append(f"当前情绪：{sentiment_label} ({sentiment:.2f})")

        # 资源状况（如果有）
        if agent.resources:
            lines.append("资源状况：" + ", ".join([f"{r.name}: {r.amount}{r.unit}" for r in agent.resources[:3]]))

        # 记忆上下文
        if agent.memory.short_term:
            recent_memories = agent.memory.get_recent_context(limit=3)
            if recent_memories:
                lines.append(f"\n最近记忆：\n{recent_memories}")

        return "\n".join(lines)

    def build_relationships_context(
        self,
        agent: Agent,
        all_agents: list[Agent]
    ) -> str:
        """构建关系上下文"""
        if not agent.relationships:
            return "暂无明确关系"

        lines = []
        for rel in agent.relationships:
            target = next((a for a in all_agents if a.id == rel.target_agent_id), None)
            if target:
                strength_label = "友好" if rel.strength > 0.3 else "敌对" if rel.strength < -0.3 else "中立"
                rel_type_label = {
                    RelationType.COMPETITOR: "竞争关系",
                    RelationType.COOPERATIVE: "合作关系",
                    RelationType.SUPPLY: "供应关系",
                    RelationType.DEMAND: "需求关系",
                    RelationType.REGULATE: "监管关系",
                    RelationType.INFLUENCE: "影响关系",
                    RelationType.NEUTRAL: "中立关系",
                }.get(rel.type, "未知关系")

                lines.append(
                    f"- {target.name}：{rel_type_label}（{strength_label}，强度: {rel.strength:.0%}）"
                )

        return "\n".join(lines) if lines else "暂无关系"

    def build_events_context(self, recent_events: list[Event], all_agents: list[Agent]) -> str:
        """构建事件上下文"""
        if not recent_events:
            return "暂无重大事件"

        lines = []
        for ev in recent_events[-5:]:
            # 获取涉及 agent 名称
            agent_names = []
            for agent_id in ev.involved_agents:
                agent = next((a for a in all_agents if a.id == agent_id), None)
                if agent:
                    agent_names.append(agent.name)

            event_type_label = {
                EventType.ACTION: "行动",
                EventType.REACTION: "反应",
                EventType.EXTERNAL: "外部",
                EventType.INTERVENTION: "干预",
                EventType.SYSTEM: "系统"
            }.get(ev.type, "未知")

            lines.append(
                f"- 第{ev.round}回合[{event_type_label}]：{ev.description[:50]}"
                + ("..." if len(ev.description) > 50 else "")
            )

        return "\n".join(lines) if lines else "暂无重大事件"

    def decide_action(
        self,
        agent: Agent,
        all_agents: list[Agent],
        recent_events: list[Event],
        current_round: int,
        global_params: dict = None,
        knowledge_context: str = ""
    ) -> ActionResult:
        """
        决定 Agent 在当前回合应该采取的行动

        决策流程：
        1. 构建完整上下文
        2. 调用 LLM 进行决策
        3. 生成行动描述
        """
        # 基础情况
        situation = self.build_situation_summary(agent, all_agents, recent_events, current_round)

        # 关系上下文
        situation += "\n\n【关系网络】\n" + self.build_relationships_context(agent, all_agents)

        # 事件上下文
        situation += "\n\n【近期事件】\n" + self.build_events_context(recent_events, all_agents)

        # 全局参数
        if global_params:
            situation += "\n\n【全局环境】\n" + ", ".join([f"{k}: {v}" for k, v in global_params.items()])

        # 可用动作
        available_actions = self.get_available_actions(agent)

        # 获取记忆中的历史决策模式
        recent_history = agent.memory.get_recent_context(limit=3)

        # 关系列表
        relationships = [
            {
                "target": rel.target_agent_id,
                "type": rel.type.value if hasattr(rel.type, 'value') else str(rel.type),
                "strength": rel.strength
            }
            for rel in agent.relationships
        ]

        # 调用 LLM 决策
        decision = self.llm.decide_action(
            agent_name=agent.name,
            agent_type=agent.type.value if hasattr(agent.type, 'value') else str(agent.type),
            agent_personality=agent.personality,
            agent_personality_traits={
                "openness": agent.personality_traits.openness,
                "conscientiousness": agent.personality_traits.conscientiousness,
                "extraversion": agent.personality_traits.extraversion,
                "agreeableness": agent.personality_traits.agreeableness,
                "neuroticism": agent.personality_traits.neuroticism
            },
            agent_goals=agent.goals,
            current_situation=situation,
            available_actions=available_actions,
            knowledge_context=knowledge_context,
            recent_history=recent_history,
            relationships=relationships
        )

        action = decision.get("action", "观望")
        if action not in available_actions:
            # 如果决策的动作不在列表中，选择一个类似的
            action = available_actions[0]

        # 生成行动描述
        context = f"第 {current_round} 回合 | {agent.name} 采取行动"
        target_agents = decision.get("target_agents", [])
        action_intensity = decision.get("action_intensity", 0.5)

        event_desc = self.llm.generate_action_description(
            agent_name=agent.name,
            action=action,
            context=context,
            target_agents=target_agents,
            action_intensity=action_intensity
        )

        return ActionResult(
            action=action,
            reasoning=decision.get("reasoning", ""),
            expected_outcome=decision.get("expected_outcome", ""),
            sentiment_change=decision.get("sentiment_change", 0),
            target_agents=target_agents,
            event_description=event_desc,
            action_intensity=action_intensity,
            risk_level=decision.get("risk_level", "medium"),
            cascade_possible=decision.get("cascade_possible", False)
        )

    def apply_action_result(
        self,
        agent: Agent,
        result: ActionResult,
        all_agents: list[Agent],
        current_round: int,
        config: SimulationConfig = None
    ) -> tuple[Event, list[tuple[Agent, float]]]:
        """
        应用行动结果

        Returns:
            (created_event, list of (affected_agent, sentiment_change))
        """
        # 更新 Agent 的行动统计
        agent.last_action_round = current_round
        agent.action_count += 1

        # 记录记忆
        memory_entry = MemoryEntry(
            round=current_round,
            type="action",
            content=f"{agent.name} 采取了「{result.action}」行动：{result.event_description}",
            emotional_valence=result.sentiment_change,
            importance=0.7
        )
        agent.memory.add_entry(memory_entry)

        # 创建事件
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.ACTION,
            description=result.event_description,
            timestamp=int(time.time() * 1000),
            round=current_round,
            involved_agents=[agent.id] + [
                a.id for a in all_agents if a.name in result.target_agents
            ],
            impact=EventImpact(
                affected_agents=result.target_agents,
                sentiment_change={agent.id: result.sentiment_change}
            ),
            action_taken=result.action,
            action_result=result.expected_outcome,
            consequence_severity=result.action_intensity,
            duration="短期" if result.action_intensity < 0.5 else "中期"
        )

        # 计算影响
        sentiment_updates: list[tuple[Agent, float]] = []

        # 1. 更新自身的情绪
        self._update_agent_sentiment(agent, result.sentiment_change)
        sentiment_updates.append((agent, result.sentiment_change))

        # 2. 对目标 agent 的影响
        for target_name in result.target_agents:
            target = next((a for a in all_agents if a.name == target_name), None)
            if target:
                # 查找关系强度
                rel = agent.get_relation(target.id)
                relation_factor = abs(rel.strength) if rel else 0.5

                # 目标受到的影响
                target_sentiment_change = result.sentiment_change * relation_factor * -1  # 通常负相关
                self._update_agent_sentiment(target, target_sentiment_change)
                sentiment_updates.append((target, target_sentiment_change))

                # 更新关系强度
                if rel:
                    rel.strength += result.sentiment_change * 0.1
                    rel.strength = max(-1, min(1, rel.strength))
                    rel.interaction_count += 1
                    rel.last_interaction_round = current_round

        # 3. 连锁反应检查
        cascade_effects = []
        if result.cascade_possible and config and config.enable_cascade:
            cascade_prob = config.cascade_probability
            for other in all_agents:
                if other.id != agent.id and other.name not in result.target_agents:
                    if random.random() < cascade_prob:
                        # 随机选择一个关系影响
                        rel = other.get_relation(agent.id)
                        if rel:
                            cascade_change = result.sentiment_change * rel.strength * 0.5
                            self._update_agent_sentiment(other, cascade_change)
                            sentiment_updates.append((other, cascade_change))
                            cascade_effects.append(
                                f"{other.name} 受到连锁影响，情绪变化 {cascade_change:.2f}"
                            )

        if cascade_effects:
            event.impact.cascade_effects = cascade_effects

        # 4. 更新情感强度
        agent.emotional_intensity = min(1.0, agent.emotional_intensity + abs(result.sentiment_change) * 0.2)

        # 5. 记录行动结果信念
        agent.update_belief(
            key=f"last_action_{current_round}",
            value=result.action,
            confidence=0.9,
            source="action_result"
        )

        return event, sentiment_updates

    def _update_agent_sentiment(self, agent: Agent, sentiment_change: float):
        """更新 Agent 的情绪值"""
        sentiment_belief = agent.get_belief("sentiment")
        if sentiment_belief:
            old_value = float(sentiment_belief.value)
            new_value = max(-1, min(1, old_value + sentiment_change))
            sentiment_belief.value = new_value
            sentiment_belief.confidence = min(1.0, sentiment_belief.confidence + 0.1)
            sentiment_belief.timestamp = int(time.time() * 1000)
            sentiment_belief.source = "action_update"
        else:
            agent.beliefs.append(Belief(
                key="sentiment",
                value=max(-1, min(1, sentiment_change)),
                confidence=0.5,
                source="action_update"
            ))

    def apply_intervention(
        self,
        agent: Agent,
        intervention_type: str,
        parameter: str,
        value: str | int | float | bool | dict,
        current_round: int
    ) -> dict:
        """
        应用干预到 Agent

        Returns:
            dict with intervention results
        """
        agent.status = AgentStatus.INTERVENED
        results = {
            "beliefs_updated": [],
            "goals_added": [],
            "sentiment_change": 0
        }

        if intervention_type == "agent_state":
            if parameter == "sentiment":
                old_sentiment = float(agent.get_belief("sentiment").value) if agent.get_belief("sentiment") else 0
                new_sentiment = float(value)
                agent.update_belief("sentiment", new_sentiment, confidence=1.0, source="intervention")
                results["sentiment_change"] = new_sentiment - old_sentiment

            elif parameter == "belief":
                if isinstance(value, dict):
                    key = value.get("key", "intervention")
                    val = value.get("value", "")
                    content = value.get("content", str(val))

                    agent.update_belief(key, val, confidence=0.9, source="intervention")
                    agent.add_relationship(
                        target_id=f"intervention_{current_round}",
                        rel_type=RelationType.INFLUENCE,
                        strength=0.3
                    )
                    results["beliefs_updated"].append(key)

            elif parameter == "goal":
                if isinstance(value, str):
                    agent.goals.append(value)
                    results["goals_added"].append(value)

        elif intervention_type == "external_event":
            if isinstance(value, str):
                goal = f"应对外部事件：{value}"
                agent.goals.append(goal)
                results["goals_added"].append(goal)

                # 更新情绪
                sentiment_change = -0.2  # 外部事件通常带来负面情绪
                self._update_agent_sentiment(agent, sentiment_change)
                results["sentiment_change"] = sentiment_change

        # 记录干预记忆
        memory_entry = MemoryEntry(
            round=current_round,
            type="intervention",
            content=f"受到外部干预：{parameter} = {value}",
            emotional_valence=results["sentiment_change"],
            importance=0.9
        )
        agent.memory.add_entry(memory_entry)

        return results

    def get_agent_insight(
        self,
        agent: Agent,
        all_agents: list[Agent],
        recent_events: list[Event]
    ) -> dict:
        """获取 Agent 的洞察分析"""
        insight = {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "current_state": {},
            "key_relationships": [],
            "action_recommendations": []
        }

        # 当前状态
        sentiment = agent.get_belief("sentiment")
        if sentiment:
            insight["current_state"]["sentiment"] = float(sentiment.value)

        insight["current_state"]["goals"] = agent.goals[-3:] if agent.goals else []
        insight["current_state"]["status"] = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)

        # 关键关系
        sorted_rels = sorted(
            agent.relationships,
            key=lambda r: abs(r.strength),
            reverse=True
        )[:3]

        for rel in sorted_rels:
            target = next((a for a in all_agents if a.id == rel.target_agent_id), None)
            if target:
                insight["key_relationships"].append({
                    "name": target.name,
                    "type": rel.type.value if hasattr(rel.type, 'value') else str(rel.type),
                    "strength": rel.strength
                })

        # 行动建议
        available = self.get_available_actions(agent)[:3]
        insight["action_recommendations"] = available

        return insight
