import uuid
import math
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
    Topology,
    TopologyNode,
    TopologyEdge,
    EventImpact,
    PersonalityTraits,
    AgentMemory,
    MemoryEntry,
)


class EventParser:
    """解析事件文本并生成 Agent 网络"""

    def __init__(self, llm_client=None):
        self.llm = llm_client or get_llm_client()

    def parse(self, event_text: str, rounds: int = 10) -> tuple[list[Agent], Topology, Event]:
        """
        解析事件文本，生成 agents、拓扑网络和初始事件

        Args:
            event_text: 事件描述文本
            rounds: 推演轮数（影响布局）

        Returns:
            (agents, topology, initial_event)
        """
        # 使用 LLM 提取实体
        parsed = self.llm.parse_event_entities(event_text)
        entities = parsed.get("entities", [])
        relationships = parsed.get("relationships", [])
        event_summary = parsed.get("event_summary", event_text)

        # 如果没有提取到实体，使用默认生成
        if not entities:
            entities = self._infer_entities_from_text(event_text)

        # 生成 agents
        agents = self._generate_agents(entities, event_text, relationships)

        # 补充实体间关系
        self._apply_parsed_relationships(agents, relationships)

        # 生成拓扑网络
        topology = self._generate_topology(agents)

        # 创建初始事件
        initial_event = self._create_initial_event(event_text, agents, event_summary)

        return agents, topology, initial_event

    def _infer_entities_from_text(self, event_text: str) -> list[dict]:
        """从文本中推断可能的实体"""
        keywords = {
            "奶茶": ["company", "某奶茶品牌"],
            "涨价": ["company", "某奶茶品牌"],
            "降价": ["competitor", "竞品"],
            "政府": ["government", "政府部门"],
            "监管": ["regulator", "监管机构"],
            "消费": ["consumer", "消费者"],
            "供应商": ["supplier", "供应商"],
            "竞争": ["competitor", "竞争对手"],
        }

        entities = []
        for keyword, (etype, ename) in keywords.items():
            if keyword in event_text and not any(e.get("name") == ename for e in entities):
                entities.append({"name": ename, "type": etype, "description": f"从'{keyword}'推断"})

        return entities

    def _generate_agents(
        self,
        entities: list[dict],
        context: str,
        relationships: list[dict]
    ) -> list[Agent]:
        """从解析的实体生成 Agent 对象"""
        agents = []
        n = max(len(entities), 3)

        # 构建已有 agent 信息用于上下文
        existing_agents_info = []

        # 布局：使用椭圆布局，重要节点放中心
        for i, entity in enumerate(entities):
            name = entity.get("name", f"Entity_{i+1}")
            entity_type = self._map_entity_type(entity.get("type", ""))

            # 生成个性
            personality_data = self.llm.generate_agent_personality(
                agent_type=entity_type.value,
                context=context,
                name=name,
                existing_agents=existing_agents_info
            )

            # 计算位置（椭圆布局）
            angle = 2 * math.pi * i / n
            radius_x = 40 + 10 * (n > 5)
            radius_y = 30 + 8 * (n > 5)
            x = 50 + radius_x * math.cos(angle)
            y = 50 + radius_y * math.sin(angle)

            # 构建信念
            beliefs = []
            for b in personality_data.get("beliefs", []):
                beliefs.append(Belief(
                    key=b.get("key", "unknown"),
                    value=b.get("value", ""),
                    confidence=b.get("confidence", 0.5),
                    source="generation"
                ))

            # 添加默认情感信念
            beliefs.append(Belief(
                key="sentiment",
                value=0.0,
                confidence=0.5,
                source="initial",
                tags=["emotion"]
            ))

            # 添加市场感知信念
            beliefs.append(Belief(
                key="market_perception",
                value="neutral",
                confidence=0.3,
                source="initial",
                tags=["market"]
            ))

            # 构建性格特征
            traits_data = personality_data.get("personality_traits", {})
            personality_traits = PersonalityTraits(
                openness=traits_data.get("openness", 0.5),
                conscientiousness=traits_data.get("conscientiousness", 0.5),
                extraversion=traits_data.get("extraversion", 0.5),
                agreeableness=traits_data.get("agreeableness", 0.5),
                neuroticism=traits_data.get("neuroticism", 0.5)
            )

            # 初始化记忆
            memory = AgentMemory()

            agent = Agent(
                id=str(uuid.uuid4()),
                name=name,
                type=entity_type,
                description=personality_data.get("description", entity.get("description", "")),
                personality=personality_data.get("personality", "中立"),
                personality_traits=personality_traits,
                goals=personality_data.get("goals", []),
                current_strategy=personality_data.get("strategy", "balanced"),
                beliefs=beliefs,
                relationships=[],
                status=AgentStatus.ACTIVE,
                memory=memory,
                position_x=x,
                position_y=y,
                created_round=0
            )

            agents.append(agent)
            existing_agents_info.append({"name": name, "type": entity_type.value})

        # 如果没有实体，创建默认 agents
        if not agents:
            agents = self._create_default_agents(context)

        # 创建基于类型的关系
        self._create_relationships(agents)

        return agents

    def _apply_parsed_relationships(
        self,
        agents: list[Agent],
        relationships: list[dict]
    ):
        """应用从文本解析出的关系"""
        for rel in relationships:
            source_name = rel.get("source", "")
            target_name = rel.get("target", "")
            rel_type_str = rel.get("type", "neutral")
            strength = rel.get("strength", 0.3)

            source_agent = next((a for a in agents if source_name in a.name), None)
            target_agent = next((a for a in agents if target_name in a.name), None)

            if source_agent and target_agent:
                rel_type = self._map_relation_type(rel_type_str)

                # 添加或更新关系
                existing = source_agent.get_relation(target_agent.id)
                if existing:
                    existing.type = rel_type
                    existing.strength = max(-1, min(1, strength))
                else:
                    source_agent.relationships.append(Relationship(
                        target_agent_id=target_agent.id,
                        type=rel_type,
                        strength=max(-1, min(1, strength)),
                        created_round=0
                    ))

    def _create_default_agents(self, context: str) -> list[Agent]:
        """当解析失败时创建默认 agents"""
        default_configs = [
            {"type": AgentType.COMPANY, "name": "XX企业", "desc": "市场主要参与者"},
            {"type": AgentType.COMPETITOR, "name": "YY竞品", "desc": "市场竞争对手"},
            {"type": AgentType.CONSUMER, "name": "消费者群体", "desc": "消费大众"},
        ]

        agents = []
        for i, config in enumerate(default_configs):
            personality_data = self.llm.generate_agent_personality(
                agent_type=config["type"].value,
                context=context,
                name=config["name"]
            )

            angle = 2 * math.pi * i / len(default_configs)
            x = 50 + 40 * math.cos(angle)
            y = 50 + 40 * math.sin(angle)

            traits_data = personality_data.get("personality_traits", {})
            personality_traits = PersonalityTraits(
                openness=traits_data.get("openness", 0.5),
                conscientiousness=traits_data.get("conscientiousness", 0.5),
                extraversion=traits_data.get("extraversion", 0.5),
                agreeableness=traits_data.get("agreeableness", 0.5),
                neuroticism=traits_data.get("neuroticism", 0.5)
            )

            agent = Agent(
                id=str(uuid.uuid4()),
                name=config["name"],
                type=config["type"],
                description=personality_data.get("description", config["desc"]),
                personality=personality_data.get("personality", "中立"),
                personality_traits=personality_traits,
                goals=personality_data.get("goals", ["发展", "竞争"]),
                beliefs=[
                    Belief(key="sentiment", value=0.0, confidence=0.5),
                    Belief(key="market_perception", value="neutral", confidence=0.3)
                ],
                relationships=[],
                status=AgentStatus.ACTIVE,
                memory=AgentMemory(),
                position_x=x,
                position_y=y,
                created_round=0
            )
            agents.append(agent)

        self._create_relationships(agents)
        return agents

    def _create_relationships(self, agents: list[Agent]):
        """根据 Agent 类型创建关系"""
        for i, agent in enumerate(agents):
            for j, other in enumerate(agents):
                if i == j:
                    continue

                rel_type = RelationType.NEUTRAL
                strength = 0.0

                # 基于类型的逻辑
                if agent.type == AgentType.COMPANY and other.type == AgentType.COMPETITOR:
                    rel_type = RelationType.COMPETITOR
                    strength = -0.4
                elif agent.type == AgentType.COMPETITOR and other.type == AgentType.COMPANY:
                    rel_type = RelationType.COMPETITOR
                    strength = -0.4
                elif agent.type == AgentType.COMPANY and other.type == AgentType.SUPPLIER:
                    rel_type = RelationType.SUPPLY
                    strength = 0.3
                elif agent.type == AgentType.SUPPLIER and other.type == AgentType.COMPANY:
                    rel_type = RelationType.DEMAND
                    strength = 0.3
                elif agent.type == AgentType.COMPANY and other.type == AgentType.CONSUMER:
                    rel_type = RelationType.DEMAND
                    strength = 0.2
                elif agent.type == AgentType.CONSUMER and other.type == AgentType.COMPANY:
                    rel_type = RelationType.SUPPLY
                    strength = 0.2
                elif agent.type == AgentType.REGULATOR and other.type == AgentType.COMPANY:
                    rel_type = RelationType.REGULATE
                    strength = -0.2
                elif agent.type == AgentType.GOVERNMENT:
                    rel_type = RelationType.INFLUENCE
                    strength = 0.1
                elif agent.type == AgentType.ORGANIZATION:
                    rel_type = RelationType.INFLUENCE
                    strength = 0.1

                if rel_type != RelationType.NEUTRAL:
                    # 检查是否已存在
                    if not agent.get_relation(other.id):
                        agent.relationships.append(Relationship(
                            target_agent_id=other.id,
                            type=rel_type,
                            strength=strength,
                            created_round=0
                        ))

    def _generate_topology(self, agents: list[Agent]) -> Topology:
        """从 agents 生成网络拓扑"""
        nodes = []
        edges = []

        # 节点
        for agent in agents:
            nodes.append(TopologyNode(
                id=f"node_{agent.id}",
                agent_id=agent.id,
                label=agent.name,
                type=agent.type,
                x=agent.position_x or 0,
                y=agent.position_y or 0
            ))

        # 边
        for agent in agents:
            for rel in agent.relationships:
                target_node_id = f"node_{rel.target_agent_id}"
                source_node_id = f"node_{agent.id}"

                # 避免重复边
                exists = any(
                    (e.source == source_node_id and e.target == target_node_id) or
                    (e.source == target_node_id and e.target == source_node_id)
                    for e in edges
                )

                if not exists:
                    edges.append(TopologyEdge(
                        source=source_node_id,
                        target=target_node_id,
                        relation=rel.type,
                        weight=abs(rel.strength),
                        label=rel.type.value if hasattr(rel.type, 'value') else str(rel.type)
                    ))

        return Topology(nodes=nodes, edges=edges)

    def _create_initial_event(
        self,
        event_text: str,
        agents: list[Agent],
        summary: str
    ) -> Event:
        """创建初始事件"""
        return Event(
            id=str(uuid.uuid4()),
            type=EventType.EXTERNAL,
            description=summary or event_text,
            timestamp=int(uuid.uuid1().time),
            round=0,
            involved_agents=[a.id for a in agents],
            impact=EventImpact(
                affected_agents=[a.id for a in agents],
                sentiment_change={a.id: 0.0 for a in agents},
            ),
            consequence_severity=0.5,
            duration="短期",
            is_reversible=True
        )

    def _map_entity_type(self, entity_type: str) -> AgentType:
        """字符串类型映射到 AgentType"""
        mapping = {
            "company": AgentType.COMPANY,
            "government": AgentType.GOVERNMENT,
            "consumer": AgentType.CONSUMER,
            "competitor": AgentType.COMPETITOR,
            "regulator": AgentType.REGULATOR,
            "supplier": AgentType.SUPPLIER,
            "individual": AgentType.INDIVIDUAL,
            "organization": AgentType.ORGANIZATION,
        }
        return mapping.get(entity_type.lower(), AgentType.ORGANIZATION)

    def _map_relation_type(self, rel_type: str) -> RelationType:
        """字符串类型映射到 RelationType"""
        mapping = {
            "competitor": RelationType.COMPETITOR,
            "cooperative": RelationType.COOPERATIVE,
            "supply": RelationType.SUPPLY,
            "demand": RelationType.DEMAND,
            "regulate": RelationType.REGULATE,
            "influence": RelationType.INFLUENCE,
            "neutral": RelationType.NEUTRAL,
            "ownership": RelationType.OWNERSHIP,
        }
        return mapping.get(rel_type.lower(), RelationType.NEUTRAL)

    def add_agent_to_simulation(
        self,
        simulation: "Simulation",
        name: str,
        agent_type: AgentType,
        description: str = ""
    ) -> Agent:
        """动态添加 Agent 到现有仿真"""
        personality_data = self.llm.generate_agent_personality(
            agent_type=agent_type.value,
            context=simulation.description,
            name=name,
            existing_agents=[{"name": a.name, "type": a.type.value} for a in simulation.agents]
        )

        # 计算位置（添加到现有布局）
        n = len(simulation.agents) + 1
        i = n - 1
        angle = 2 * math.pi * i / max(n, 3)
        x = 50 + 40 * math.cos(angle)
        y = 50 + 40 * math.sin(angle)

        traits_data = personality_data.get("personality_traits", {})
        personality_traits = PersonalityTraits(
            openness=traits_data.get("openness", 0.5),
            conscientiousness=traits_data.get("conscientiousness", 0.5),
            extraversion=traits_data.get("extraversion", 0.5),
            agreeableness=traits_data.get("agreeableness", 0.5),
            neuroticism=traits_data.get("neuroticism", 0.5)
        )

        agent = Agent(
            id=str(uuid.uuid4()),
            name=name,
            type=agent_type,
            description=personality_data.get("description", description),
            personality=personality_data.get("personality", "中立"),
            personality_traits=personality_traits,
            goals=personality_data.get("goals", []),
            beliefs=[
                Belief(key="sentiment", value=0.0, confidence=0.5),
                Belief(key="market_perception", value="neutral", confidence=0.3)
            ],
            relationships=[],
            status=AgentStatus.ACTIVE,
            memory=AgentMemory(),
            position_x=x,
            position_y=y,
            created_round=simulation.current_round
        )

        # 与现有 agents 建立关系
        for existing in simulation.agents:
            rel_type = self._infer_relation_type(agent.type, existing.type)
            if rel_type != RelationType.NEUTRAL:
                agent.relationships.append(Relationship(
                    target_agent_id=existing.id,
                    type=rel_type,
                    strength=0.2,
                    created_round=simulation.current_round
                ))
                existing.relationships.append(Relationship(
                    target_agent_id=agent.id,
                    type=rel_type,
                    strength=0.2,
                    created_round=simulation.current_round
                ))

        # 添加到拓扑
        simulation.agents.append(agent)
        simulation.topology.nodes.append(TopologyNode(
            id=f"node_{agent.id}",
            agent_id=agent.id,
            label=agent.name,
            type=agent.type,
            x=x,
            y=y
        ))

        return agent

    def _infer_relation_type(self, type1: AgentType, type2: AgentType) -> RelationType:
        """推断两个 Agent 类型之间的关系"""
        if type1 == AgentType.COMPETITOR or type2 == AgentType.COMPETITOR:
            if type1 in (AgentType.COMPANY, AgentType.COMPETITOR) or type2 in (AgentType.COMPANY, AgentType.COMPETITOR):
                return RelationType.COMPETITOR
        if type1 == AgentType.SUPPLIER or type2 == AgentType.SUPPLIER:
            return RelationType.SUPPLY
        if type1 == AgentType.CONSUMER or type2 == AgentType.CONSUMER:
            return RelationType.DEMAND
        if type1 == AgentType.REGULATOR or type2 == AgentType.REGULATOR:
            return RelationType.REGULATE
        return RelationType.NEUTRAL
