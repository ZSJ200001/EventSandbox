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
)


class EventParser:
    """Parses event text and generates agents and topology."""

    def __init__(self, llm_client=None):
        self.llm = llm_client or get_llm_client()

    def parse(self, event_text: str) -> tuple[list[Agent], Topology, Event]:
        """Parse event text and generate agents, topology, and initial event."""
        # Use LLM to extract entities
        parsed = self.llm.parse_event_entities(event_text)

        # Generate agents
        agents = self._generate_agents(parsed.get("entities", []), event_text)

        # Generate topology
        topology = self._generate_topology(agents, parsed.get("relationships", []))

        # Create initial event
        initial_event = Event(
            id=str(uuid.uuid4()),
            type=EventType.EXTERNAL,
            description=event_text,
            timestamp=int(uuid.uuid1().time),
            round=0,
            involved_agents=[a.id for a in agents],
            impact=EventImpact(
                affected_agents=[a.id for a in agents],
                sentiment_change={a.id: 0.0 for a in agents},
            ),
        )

        return agents, topology, initial_event

    def _generate_agents(
        self, entities: list[dict], context: str
    ) -> list[Agent]:
        """Generate Agent objects from parsed entities."""
        agents = []
        n = len(entities) if entities else 3

        # Layout agents in a circle
        for i, entity in enumerate(entities):
            name = entity.get("name", f"Agent_{i+1}")
            entity_type = self._map_entity_type(entity.get("type", ""))

            # Generate personality using LLM
            personality_data = self.llm.generate_agent_personality(
                agent_type=entity_type.value,
                context=context,
                name=name,
            )

            # Calculate position in circle
            angle = 2 * math.pi * i / n
            x = 50 + 40 * math.cos(angle)
            y = 50 + 40 * math.sin(angle)

            beliefs = []
            for b in personality_data.get("beliefs", []):
                beliefs.append(
                    Belief(
                        key=b.get("key", "unknown"),
                        value=b.get("value", ""),
                        confidence=b.get("confidence", 0.5),
                    )
                )

            # Add default sentiment belief
            beliefs.append(Belief(key="sentiment", value=0.0, confidence=0.5))

            agent = Agent(
                id=str(uuid.uuid4()),
                name=name,
                type=entity_type,
                description=personality_data.get("description", entity.get("description", "")),
                personality=personality_data.get("personality", "neutral"),
                goals=personality_data.get("goals", []),
                beliefs=beliefs,
                relationships=[],
                status=AgentStatus.ACTIVE,
                position_x=x,
                position_y=y,
            )
            agents.append(agent)

        # If no entities, create default agents based on context
        if not agents:
            agents = self._create_default_agents(context)

        # Create relationships between agents
        self._create_relationships(agents)

        return agents

    def _create_default_agents(self, context: str) -> list[Agent]:
        """Create default agents when parsing fails."""
        default_types = [
            AgentType.COMPANY,
            AgentType.COMPETITOR,
            AgentType.CONSUMER,
        ]

        agents = []
        for i, agent_type in enumerate(default_types):
            name = f"{agent_type.value.title()}_{i+1}"
            personality_data = self.llm.generate_agent_personality(
                agent_type=agent_type.value,
                context=context,
                name=name,
            )

            angle = 2 * math.pi * i / len(default_types)
            x = 50 + 40 * math.cos(angle)
            y = 50 + 40 * math.sin(angle)

            agent = Agent(
                id=str(uuid.uuid4()),
                name=name,
                type=agent_type,
                description=personality_data.get("description", ""),
                personality=personality_data.get("personality", "neutral"),
                goals=personality_data.get("goals", ["survive", "grow"]),
                beliefs=[Belief(key="sentiment", value=0.0, confidence=0.5)],
                relationships=[],
                status=AgentStatus.ACTIVE,
                position_x=x,
                position_y=y,
            )
            agents.append(agent)

        self._create_relationships(agents)
        return agents

    def _create_relationships(self, agents: list[Agent]):
        """Create relationships between agents based on their types."""
        for i, agent in enumerate(agents):
            for j, other in enumerate(agents):
                if i == j:
                    continue

                # Determine relationship type based on agent types
                rel_type = RelationType.NEUTRAL
                strength = 0.0

                if agent.type in [AgentType.COMPETITOR] and other.type in [
                    AgentType.COMPETITOR,
                    AgentType.COMPANY,
                ]:
                    rel_type = RelationType.COMPETITOR
                    strength = -0.5
                elif agent.type == AgentType.SUPPLIER and other.type == AgentType.COMPANY:
                    rel_type = RelationType.SUPPLY
                    strength = 0.3
                elif agent.type == AgentType.CONSUMER and other.type == AgentType.COMPANY:
                    rel_type = RelationType.DEMAND
                    strength = 0.2
                elif agent.type == AgentType.REGULATOR or other.type == AgentType.REGULATOR:
                    rel_type = RelationType.REGULATE
                    strength = -0.2

                if rel_type != RelationType.NEUTRAL:
                    agent.relationships.append(
                        Relationship(
                            target_agent_id=other.id,
                            type=rel_type,
                            strength=strength,
                        )
                    )

    def _map_entity_type(self, entity_type: str) -> AgentType:
        """Map string entity type to AgentType enum."""
        type_mapping = {
            "company": AgentType.COMPANY,
            "government": AgentType.GOVERNMENT,
            "consumer": AgentType.CONSUMER,
            "competitor": AgentType.COMPETITOR,
            "regulator": AgentType.REGULATOR,
            "supplier": AgentType.SUPPLIER,
            "individual": AgentType.INDIVIDUAL,
            "organization": AgentType.ORGANIZATION,
        }
        return type_mapping.get(entity_type.lower(), AgentType.ORGANIZATION)

    def _generate_topology(
        self, agents: list[Agent], relationships: list[dict]
    ) -> Topology:
        """Generate network topology from agents and relationships."""
        nodes = []
        edges = []

        # Create nodes
        for agent in agents:
            nodes.append(
                TopologyNode(
                    id=f"node_{agent.id}",
                    agent_id=agent.id,
                    label=agent.name,
                    type=agent.type,
                )
            )

        # Create edges from relationships
        for agent in agents:
            for rel in agent.relationships:
                edges.append(
                    TopologyEdge(
                        source=f"node_{agent.id}",
                        target=f"node_{rel.target_agent_id}",
                        relation=rel.type,
                        weight=abs(rel.strength),
                    )
                )

        # Add edges from parsed relationships if not already added
        for rel in relationships:
            source_name = rel.get("source", "")
            target_name = rel.get("target", "")
            rel_type_str = rel.get("type", "neutral")

            source_agent = next((a for a in agents if a.name == source_name), None)
            target_agent = next((a for a in agents if a.name == target_name), None)

            if source_agent and target_agent:
                rel_type = self._map_relation_type(rel_type_str)
                strength = rel.get("strength", 0.5)

                # Check if edge already exists
                exists = any(
                    e.source == f"node_{source_agent.id}"
                    and e.target == f"node_{target_agent.id}"
                    for e in edges
                )

                if not exists:
                    edges.append(
                        TopologyEdge(
                            source=f"node_{source_agent.id}",
                            target=f"node_{target_agent.id}",
                            relation=rel_type,
                            weight=abs(strength),
                        )
                    )

        return Topology(nodes=nodes, edges=edges)

    def _map_relation_type(self, rel_type: str) -> RelationType:
        """Map string relation type to RelationType enum."""
        type_mapping = {
            "competitor": RelationType.COMPETITOR,
            "cooperative": RelationType.COOPERATIVE,
            "supply": RelationType.SUPPLY,
            "demand": RelationType.DEMAND,
            "regulate": RelationType.REGULATE,
            "influence": RelationType.INFLUENCE,
            "neutral": RelationType.NEUTRAL,
        }
        return type_mapping.get(rel_type.lower(), RelationType.NEUTRAL)
