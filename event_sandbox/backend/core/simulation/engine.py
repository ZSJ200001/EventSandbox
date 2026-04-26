import uuid
import time
import random
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.agent import AgentEngine
from core.event_parser import EventParser
from core.knowledge import KnowledgeGraph
from core.llm import get_llm_client
from models.entities import (
    Simulation,
    SimulationConfig,
    SimulationStatus,
    SimulationMetrics,
    Event,
    EventType,
    EventImpact,
    Intervention,
    InterventionType,
    Agent,
    AgentStatus,
)


class SimulationEngine:
    """仿真引擎 - 核心调度器"""

    def __init__(
        self,
        llm_client=None,
        knowledge_graph: Optional[KnowledgeGraph] = None,
    ):
        self.llm = llm_client or get_llm_client()
        self.agent_engine = AgentEngine(self.llm)
        self.event_parser = EventParser(self.llm)
        self.knowledge = knowledge_graph or KnowledgeGraph()
        self.simulations: dict[str, Simulation] = {}

    def create_simulation(
        self,
        name: str,
        description: str,
        event_text: str,
        config: Optional[SimulationConfig] = None,
        rounds: int = 10
    ) -> Simulation:
        """创建新的仿真"""
        if config is None:
            config = SimulationConfig()

        # 解析事件并生成 agents
        agents, topology, initial_event = self.event_parser.parse(event_text, rounds)

        # 创建仿真
        simulation = Simulation(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            agents=agents,
            events=[initial_event],
            topology=topology,
            rounds=rounds,
            current_round=0,
            status=SimulationStatus.PENDING,
            metrics=SimulationMetrics(
                overall_sentiment=0.0,
                market_activity=0.3,
                cooperation_level=0.5,
                conflict_level=0.3,
                stability=0.8,
                innovation=0.2,
            ),
        )

        self.simulations[simulation.id] = simulation
        return simulation

    def step(
        self,
        simulation_id: str,
        intervention: Optional[Intervention] = None,
    ) -> tuple[Simulation, list[Event], list[Agent], list[dict]]:
        """
        执行一步仿真

        Returns:
            (simulation, new_events, updated_agents, action_results)
        """
        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        if simulation.status == SimulationStatus.COMPLETED:
            raise ValueError("Simulation has already completed")

        # 更新状态
        simulation.status = SimulationStatus.RUNNING
        simulation.current_round += 1
        current_round = simulation.current_round

        # 确保开始时间已设置
        if simulation.start_time is None:
            simulation.start_time = int(time.time() * 1000)

        new_events = []
        updated_agents = []
        action_results = []

        # 全局参数
        global_params = {
            "market_sentiment": simulation.global_sentiment,
            "round": current_round,
            "market_conditions": simulation.market_conditions or "neutral"
        }

        # 处理干预
        pending_interventions = self._collect_pending_interventions(simulation, intervention)

        for int_obj in pending_interventions:
            self._apply_intervention(simulation, int_obj)
            int_event = Event(
                id=str(uuid.uuid4()),
                type=EventType.INTERVENTION,
                description=self._describe_intervention(int_obj),
                timestamp=int(time.time() * 1000),
                round=current_round,
                involved_agents=[int_obj.target] if int_obj.target else [],
                impact=EventImpact(),
                consequence_severity=0.6,
                duration="短期",
                is_reversible=False
            )
            new_events.append(int_event)
            simulation.interventions.append({
                "id": int_obj.id,
                "type": int_obj.type,
                "value": int_obj.value,
                "round": current_round
            })

        # 随机事件检查
        if config.enable_random_events if hasattr(self, 'config') and self.config else True:
            if random.random() < 0.1:  # 10% 概率
                random_event = self._generate_random_event(simulation, current_round)
                if random_event:
                    new_events.append(random_event)

        # 每个 Agent 决策和行动
        for agent in simulation.get_active_agents():
            try:
                # 获取知识上下文
                knowledge_context = self.knowledge.get_knowledge_context(
                    agent, simulation.agents
                )

                # 决策
                result = self.agent_engine.decide_action(
                    agent=agent,
                    all_agents=simulation.agents,
                    recent_events=simulation.events[-10:],
                    current_round=current_round,
                    global_params=global_params,
                    knowledge_context=knowledge_context
                )

                # 应用行动结果
                event, sentiment_updates = self.agent_engine.apply_action_result(
                    agent, result, simulation.agents, current_round, self.config
                )
                event.round = current_round
                new_events.append(event)

                # 记录行动结果
                action_results.append({
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "action": result.action,
                    "description": result.event_description,
                    "sentiment_change": result.sentiment_change,
                    "reasoning": result.reasoning
                })

                # 跟踪更新
                for updated_agent, _ in sentiment_updates:
                    if updated_agent.id not in [a.id for a in updated_agents]:
                        updated_agents.append(updated_agent)

                # 验证动作
                valid, msg = self.knowledge.validate_action(agent, result.action)
                if not valid:
                    event.description = f"[受限]{event.description}"

            except Exception as e:
                # 单个 agent 出错不影响整体
                action_results.append({
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "error": str(e)
                })

        # 更新指标
        self._update_metrics(simulation)

        # 添加新事件
        simulation.events.extend(new_events)

        # 检查结束条件
        end_reason = self._check_end_conditions(simulation)
        if end_reason:
            simulation.status = SimulationStatus.COMPLETED
            simulation.end_time = int(time.time() * 1000)
            # 添加结束事件
            end_event = Event(
                id=str(uuid.uuid4()),
                type=EventType.SYSTEM,
                description=f"仿真结束：{end_reason}",
                timestamp=int(time.time() * 1000),
                round=current_round,
                involved_agents=[],
                impact=EventImpact()
            )
            simulation.events.append(end_event)

        return simulation, new_events, updated_agents, action_results

    def batch_step(
        self,
        simulation_id: str,
        steps: int = 5,
        intervention: Optional[Intervention] = None,
        stop_on_condition: str = None,
        sentiment_threshold: float = 0.8,
        conflict_threshold: float = 0.8
    ) -> tuple[Simulation, int, list[Event], str]:
        """
        批量执行多步

        Returns:
            (simulation, steps_executed, all_events, stop_reason)
        """
        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        all_events = []
        steps_executed = 0
        stop_reason = "completed"

        for i in range(steps):
            if simulation.status == SimulationStatus.COMPLETED:
                stop_reason = "reached_end"
                break

            try:
                _, new_events, _, _ = self.step(simulation_id, intervention if i == 0 else None)
                all_events.extend(new_events)
                steps_executed += 1

                # 检查停止条件
                if stop_on_condition:
                    if stop_on_condition == "sentiment_threshold":
                        if abs(simulation.metrics.overall_sentiment) >= sentiment_threshold:
                            stop_reason = "sentiment_threshold_reached"
                            break
                    elif stop_on_condition == "conflict_threshold":
                        if simulation.metrics.conflict_level >= conflict_threshold:
                            stop_reason = "conflict_threshold_reached"
                            break

            except Exception as e:
                stop_reason = f"error: {str(e)}"
                break

        return simulation, steps_executed, all_events, stop_reason

    def _collect_pending_interventions(
        self,
        simulation: Simulation,
        intervention: Optional[Intervention]
    ) -> list[Intervention]:
        """收集待处理的干预"""
        pending = []

        # 处理立即干预
        if intervention:
            if intervention.delay > 0:
                # 延迟干预 - 存储但暂不应用
                simulation.interventions.append({
                    "id": intervention.id,
                    "type": intervention.type,
                    "value": intervention.value,
                    "delay": intervention.delay,
                    "target": intervention.target,
                    "round": simulation.current_round + intervention.delay,
                    "is_active": False
                })
            else:
                pending.append(intervention)

        # 检查延迟干预是否到期
        current_round = simulation.current_round
        for int_data in simulation.interventions:
            if isinstance(int_data, dict):
                if not int_data.get("is_active", True):
                    if int_data.get("round", 0) <= current_round:
                        # 激活延迟干预
                        int_data["is_active"] = True
                        pending.append(Intervention(
                            id=int_data["id"],
                            type=int_data["type"],
                            value=int_data["value"],
                            target=int_data.get("target"),
                            timestamp=int(time.time() * 1000),
                            round=current_round
                        ))

        return pending

    def _apply_intervention(
        self, simulation: Simulation, intervention: Intervention
    ):
        """应用干预到仿真"""
        if intervention.type == InterventionType.GLOBAL_PARAM:
            # 全局参数调整
            param = intervention.parameter or "global_sentiment"
            simulation.market_conditions = simulation.market_conditions or {}
            simulation.market_conditions[param] = intervention.value

            if param == "global_sentiment":
                simulation.global_sentiment = float(intervention.value)

        elif intervention.type == InterventionType.AGENT_STATE:
            if intervention.target:
                agent = simulation.get_agent(intervention.target)
                if agent:
                    self.agent_engine.apply_intervention(
                        agent,
                        intervention.type.value,
                        intervention.parameter or "belief",
                        intervention.value,
                        simulation.current_round
                    )

        elif intervention.type == InterventionType.EXTERNAL_EVENT:
            external_event = Event(
                id=str(uuid.uuid4()),
                type=EventType.EXTERNAL,
                description=str(intervention.value),
                timestamp=int(time.time() * 1000),
                round=simulation.current_round,
                involved_agents=[intervention.target] if intervention.target else [],
                impact=EventImpact(),
                consequence_severity=0.7,
                duration="中期",
                is_reversible=True
            )
            simulation.events.append(external_event)

        elif intervention.type == InterventionType.ADD_AGENT:
            # 动态添加 Agent
            if isinstance(intervention.value, dict):
                from models.entities import AgentType
                agent = self.event_parser.add_agent_to_simulation(
                    simulation,
                    name=intervention.value.get("name", "新加入者"),
                    agent_type=AgentType(intervention.value.get("type", "individual")),
                    description=intervention.value.get("description", "")
                )
                new_event = Event(
                    id=str(uuid.uuid4()),
                    type=EventType.EXTERNAL,
                    description=f"新角色加入：{agent.name}",
                    timestamp=int(time.time() * 1000),
                    round=simulation.current_round,
                    involved_agents=[agent.id]
                )
                simulation.events.append(new_event)

    def _describe_intervention(self, intervention: Intervention) -> str:
        """生成干预描述"""
        descriptions = {
            InterventionType.GLOBAL_PARAM: f"全局参数调整：{intervention.parameter} = {intervention.value}",
            InterventionType.AGENT_STATE: f"Agent状态修改：{intervention.target} - {intervention.parameter}",
            InterventionType.EXTERNAL_EVENT: f"注入外部事件：{intervention.value}",
            InterventionType.ADD_AGENT: f"添加新Agent：{intervention.value}",
            InterventionType.REMOVE_AGENT: f"移除Agent：{intervention.target}",
            InterventionType.MODIFY_RELATION: f"修改关系：{intervention.target}",
        }
        return descriptions.get(intervention.type, "干预已应用")

    def _generate_random_event(
        self, simulation: Simulation, current_round: int
    ) -> Optional[Event]:
        """生成随机事件"""
        random_events = [
            "市场突然出现新的竞争者",
            "原材料价格波动",
            "消费者偏好发生变化",
            "行业技术革新",
            "经济环境出现变化"
        ]

        if random.random() < 0.5:
            return None

        event_desc = random.choice(random_events)

        return Event(
            id=str(uuid.uuid4()),
            type=EventType.EXTERNAL,
            description=f"【突发事件】{event_desc}",
            timestamp=int(time.time() * 1000),
            round=current_round,
            involved_agents=[],
            impact=EventImpact(
                sentiment_change={a.id: random.uniform(-0.1, 0.1) for a in simulation.agents}
            ),
            consequence_severity=0.4,
            duration="短期",
            is_reversible=True,
            is_market_wide=True
        )

    def _update_metrics(self, simulation: Simulation):
        """更新仿真指标"""
        if not simulation.agents:
            return

        # 基础指标
        sentiments = []
        active_count = 0

        for agent in simulation.agents:
            if agent.status != AgentStatus.INACTIVE:
                active_count += 1
                sentiment_belief = agent.get_belief("sentiment")
                if sentiment_belief:
                    sentiments.append(float(sentiment_belief.value))

        if sentiments:
            simulation.metrics.overall_sentiment = sum(sentiments) / len(sentiments)

        # 关系统计
        cooperative_count = 0
        conflict_count = 0
        total_rel_count = 0

        for agent in simulation.agents:
            for rel in agent.relationships:
                total_rel_count += 1
                rel_type = rel.type.value if hasattr(rel.type, 'value') else str(rel.type)
                if rel_type in ["cooperative", "supply"]:
                    cooperative_count += 1
                elif rel_type == "competitor":
                    conflict_count += 1

        if total_rel_count > 0:
            simulation.metrics.cooperation_level = cooperative_count / total_rel_count
            simulation.metrics.conflict_level = conflict_count / total_rel_count

        # 市场活跃度
        expected_events = simulation.current_round * len(simulation.agents)
        simulation.metrics.market_activity = min(1.0, len(simulation.events) / max(1, expected_events))

        # 稳定性（基于情绪波动）
        if len(sentiments) > 1:
            variance = sum((s - simulation.metrics.overall_sentiment) ** 2 for s in sentiments) / len(sentiments)
            simulation.metrics.stability = max(0, 1 - variance)

        # 创新指数（基于行动多样性）
        action_types = set()
        for event in simulation.events:
            if event.action_taken:
                action_types.add(event.action_taken)
        simulation.metrics.innovation = min(1.0, len(action_types) / max(1, simulation.current_round))

    def _check_end_conditions(self, simulation: Simulation) -> str:
        """检查结束条件"""
        # 达到最大轮数
        if simulation.current_round >= simulation.rounds:
            return "达到最大推演轮数"

        # 所有 Agent 都不活跃
        if not simulation.get_active_agents():
            return "所有Agent已不活跃"

        # 市场完全死亡
        if simulation.metrics.market_activity < 0.05:
            return "市场已完全停滞"

        return ""

    def get_simulation(self, simulation_id: str) -> Optional[Simulation]:
        """获取仿真"""
        return self.simulations.get(simulation_id)

    def delete_simulation(self, simulation_id: str) -> bool:
        """删除仿真"""
        if simulation_id in self.simulations:
            del self.simulations[simulation_id]
            return True
        return False

    def list_simulations(self, status: SimulationStatus = None) -> list[Simulation]:
        """列出仿真"""
        sims = list(self.simulations.values())
        if status:
            sims = [s for s in sims if s.status == status]
        return sorted(sims, key=lambda x: x.current_round, reverse=True)

    def pause_simulation(self, simulation_id: str) -> Simulation:
        """暂停仿真"""
        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")
        simulation.status = SimulationStatus.PAUSED
        return simulation

    def resume_simulation(self, simulation_id: str) -> Simulation:
        """恢复仿真"""
        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")
        if simulation.status != SimulationStatus.PAUSED:
            raise ValueError(f"Simulation {simulation_id} is not paused")
        simulation.status = SimulationStatus.RUNNING
        return simulation

    def compare_scenarios(
        self,
        simulation_id: str,
        intervention: Intervention,
        steps: int = 5
    ) -> dict:
        """
        对比场景（有/无干预）

        执行流程：
        1. 记录当前状态快照
        2. 克隆仿真（如果有支持）
        3. 在克隆上执行多步（有干预）
        4. 在原状态执行多步（无干预）
        5. 对比指标差异
        """
        import copy

        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        # 保存原始状态
        original_round = simulation.current_round
        original_events_count = len(simulation.events)

        # 记录基线指标
        baseline_metrics = copy.deepcopy(simulation.metrics)
        baseline_state = {
            "round": original_round,
            "sentiment": simulation.metrics.overall_sentiment,
            "activity": simulation.metrics.market_activity,
            "cooperation": simulation.metrics.cooperation_level,
            "conflict": simulation.metrics.conflict_level
        }

        # 执行有干预的步骤
        intervention_metrics_history = [baseline_state]
        try:
            for i in range(steps):
                if simulation.status == SimulationStatus.COMPLETED:
                    break
                _, _, _, _ = self.step(
                    simulation_id,
                    intervention if i == 0 else None
                )
                intervention_metrics_history.append({
                    "round": simulation.current_round,
                    "sentiment": simulation.metrics.overall_sentiment,
                    "activity": simulation.metrics.market_activity,
                    "cooperation": simulation.metrics.cooperation_level,
                    "conflict": simulation.metrics.conflict_level
                })
        except Exception as e:
            pass

        # 记录干预后的指标
        with_intervention_metrics = copy.deepcopy(simulation.metrics)
        with_intervention_state = {
            "round": simulation.current_round,
            "sentiment": simulation.metrics.overall_sentiment,
            "activity": simulation.metrics.market_activity,
            "cooperation": simulation.metrics.cooperation_level,
            "conflict": simulation.metrics.conflict_level
        }

        # 计算差异
        differences = {
            "overall_sentiment": with_intervention_metrics.overall_sentiment - baseline_metrics.overall_sentiment,
            "market_activity": with_intervention_metrics.market_activity - baseline_metrics.market_activity,
            "cooperation_level": with_intervention_metrics.cooperation_level - baseline_metrics.cooperation_level,
            "conflict_level": with_intervention_metrics.conflict_level - baseline_metrics.conflict_level,
        }

        # 计算百分比变化
        percentage_changes = {}
        for key, diff in differences.items():
            baseline_val = getattr(baseline_metrics, key, 0)
            if baseline_val != 0:
                percentage_changes[key] = (diff / abs(baseline_val)) * 100
            else:
                percentage_changes[key] = 0 if diff == 0 else float('inf')

        # 生成洞察
        insights = []
        if differences["overall_sentiment"] > 0.1:
            insights.append("干预显著提升了整体情绪")
        elif differences["overall_sentiment"] < -0.1:
            insights.append("干预导致整体情绪下降")

        if differences["conflict_level"] > 0.1:
            insights.append("干预增加了冲突程度")
        elif differences["conflict_level"] < -0.1:
            insights.append("干预有效降低了冲突")

        if differences["cooperation_level"] > 0.1:
            insights.append("干预促进了合作")
        elif differences["cooperation_level"] < -0.1:
            insights.append("干预削弱了合作关系")

        # 时间线对比
        timeline_comparison = []
        for i, (base, with_int) in enumerate(zip([baseline_state], intervention_metrics_history[1:])):
            timeline_comparison.append({
                "step": i + 1,
                "baseline": base,
                "with_intervention": with_int,
                "delta": {
                    "sentiment": with_int["sentiment"] - base["sentiment"] if i == 0 else with_int["sentiment"] - intervention_metrics_history[i]["sentiment"]
                }
            })

        return {
            "simulation_id": simulation_id,
            "baseline_metrics": baseline_metrics.model_dump(),
            "with_intervention_metrics": with_intervention_metrics.model_dump(),
            "metric_deltas": differences,
            "metric_percentage_changes": percentage_changes,
            "timeline_comparison": timeline_comparison,
            "key_insights": insights,
            "conclusion": "; ".join(insights) if insights else "干预效果不明显"
        }

    def get_agent_detail(self, simulation_id: str, agent_id: str) -> Optional[dict]:
        """获取 Agent 详细信息"""
        simulation = self.simulations.get(simulation_id)
        if not simulation:
            return None

        agent = simulation.get_agent(agent_id)
        if not agent:
            return None

        # 获取行动历史
        action_history = []
        for event in simulation.events:
            if agent.id in event.involved_agents and event.action_taken:
                action_history.append({
                    "round": event.round,
                    "action": event.action_taken,
                    "description": event.description,
                    "result": event.action_result
                })

        return {
            "agent": agent,
            "recent_memory": agent.memory.get_formatted_memory(),
            "relationship_summary": [
                {
                    "target_id": rel.target_agent_id,
                    "type": rel.type.value if hasattr(rel.type, 'value') else str(rel.type),
                    "strength": rel.strength,
                    "interaction_count": rel.interaction_count
                }
                for rel in agent.relationships
            ],
            "action_history": action_history[-10:]
        }
