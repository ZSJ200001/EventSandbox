import networkx as nx
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models.entities import Agent, AgentType, RelationType


class KnowledgeGraph:
    """Knowledge graph for constraining and guiding agent behavior."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self._initialize_base_knowledge()

    def _initialize_base_knowledge(self):
        """Initialize base domain knowledge."""
        # Agent type relationships
        type_hierarchy = {
            AgentType.COMPANY: ["supplier", "competitor", "consumer"],
            AgentType.COMPETITOR: ["company", "competitor"],
            AgentType.SUPPLIER: ["company"],
            AgentType.CONSUMER: ["company"],
            AgentType.GOVERNMENT: ["company", "organization"],
            AgentType.REGULATOR: ["company", "individual"],
        }

        # Add type nodes and edges
        for agent_type, related in type_hierarchy.items():
            self.graph.add_node(agent_type.value, type="agent_type")
            for related_type in related:
                self.graph.add_edge(
                    agent_type.value, related_type, relation="related_to"
                )

        # Relationship constraints
        relation_constraints = {
            RelationType.COMPETITOR: {
                "sentiment_range": (-1.0, -0.3),
                "allowed_actions": ["attack", "defend", "match"],
            },
            RelationType.COOPERATIVE: {
                "sentiment_range": (0.3, 1.0),
                "allowed_actions": ["support", "collaborate", "share"],
            },
            RelationType.SUPPLY: {
                "sentiment_range": (-0.2, 0.5),
                "allowed_actions": ["supply", "negotiate", "restrict"],
            },
            RelationType.DEMAND: {
                "sentiment_range": (-0.3, 0.3),
                "allowed_actions": ["buy", "complain", "recommend"],
            },
            RelationType.REGULATE: {
                "sentiment_range": (-0.5, 0.2),
                "allowed_actions": ["regulate", "penalize", "approve"],
            },
        }

        for rel_type, constraints in relation_constraints.items():
            self.graph.add_node(
                f"constraint_{rel_type.value}", type="constraint", **constraints
            )

    def add_entity(self, entity_id: str, entity_type: str, properties: dict):
        """Add an entity to the knowledge graph."""
        self.graph.add_node(entity_id, type=entity_type, **properties)

    def add_relation(
        self, source_id: str, target_id: str, relation: str, properties: dict = None
    ):
        """Add a relation between entities."""
        self.graph.add_edge(
            source_id, target_id, relation=relation, **(properties or {})
        )

    def get_agent_constraints(self, agent: Agent) -> dict:
        """Get behavioral constraints for an agent based on its relationships."""
        constraints = {
            "allowed_actions": [],
            "sentiment_bounds": (-1.0, 1.0),
            "forbidden_actions": [],
            "knowledge_context": "",
        }

        if not agent.relationships:
            # Default constraints for agents with no explicit relationships
            constraints["allowed_actions"] = ["observe", "wait", "act"]
            return constraints

        all_allowed = set()
        all_forbidden = set()
        sentiment_bounds = [1.0, -1.0]  # [min, max]

        for rel in agent.relationships:
            # Get constraint node
            constraint_node = f"constraint_{rel.type.value}"
            if self.graph.has_node(constraint_node):
                node_data = self.graph.nodes[constraint_node]
                all_allowed.update(node_data.get("allowed_actions", []))

                sent_range = node_data.get("sentiment_range", (-1, 1))
                sentiment_bounds[0] = min(sentiment_bounds[0], sent_range[0])
                sentiment_bounds[1] = max(sentiment_bounds[1], sent_range[1])

            # Add relationship-specific modifications
            if rel.type == RelationType.COMPETITOR:
                all_forbidden.update(["cooperate", "ally"])
            elif rel.type == RelationType.COOPERATIVE:
                all_forbidden.update(["attack", "sabotage"])

        constraints["allowed_actions"] = list(all_allowed) if all_allowed else ["act"]
        constraints["sentiment_bounds"] = tuple(sentiment_bounds)
        constraints["forbidden_actions"] = list(all_forbidden)

        return constraints

    def get_knowledge_context(self, agent: Agent, all_agents: list[Agent]) -> str:
        """Generate knowledge context string for an agent."""
        context_parts = []

        # Add type-based knowledge
        agent_type = agent.type if isinstance(agent.type, str) else agent.type.value
        type_knowledge = self._get_type_knowledge(agent.type)
        if type_knowledge:
            context_parts.append(f"As a {agent_type}, you should consider: {type_knowledge}")

        # Add relationship-based knowledge
        for rel in agent.relationships:
            target = next((a for a in all_agents if a.id == rel.target_agent_id), None)
            if target:
                rel_knowledge = self._get_relation_knowledge(rel.type, target.name)
                context_parts.append(rel_knowledge)

        # Add agent's own goals context
        if agent.goals:
            context_parts.append(f"Your objectives: {', '.join(agent.goals)}")

        return "\n".join(context_parts)

    def _get_type_knowledge(self, agent_type) -> str:
        """Get knowledge specific to an agent type."""
        # Convert to string if enum
        if hasattr(agent_type, 'value'):
            agent_type = agent_type.value

        type_knowledge = {
            AgentType.COMPANY: "market dynamics, profit maximization, competitive positioning, stakeholder management",
            AgentType.COMPETITOR: "market share, differentiation, strategic advantage, competitive response",
            AgentType.CONSUMER: "value optimization, product quality, brand reputation, social influence",
            AgentType.SUPPLIER: "cost efficiency, reliable delivery, quality control, relationship management",
            AgentType.GOVERNMENT: "public interest, policy objectives, regulatory compliance, public opinion",
            AgentType.REGULATOR: "fair competition, consumer protection, legal compliance, enforcement actions",
            AgentType.ORGANIZATION: "member interests, public image, advocacy goals, resource mobilization",
            AgentType.INDIVIDUAL: "personal interests, social connections, reputation, decision autonomy",
        }
        return type_knowledge.get(agent_type, "")

    def _get_relation_knowledge(self, rel_type, target_name: str) -> str:
        """Get knowledge about a specific relationship."""
        # Convert to string if enum
        if hasattr(rel_type, 'value'):
            rel_type = rel_type.value

        relation_knowledge = {
            "competitor": f"{target_name} is a competitor - consider competitive dynamics and market positioning",
            "cooperative": f"{target_name} is a partner - cooperation and mutual benefit should be considered",
            "supply": f"{target_name} is a supplier - supply chain stability and negotiation are key",
            "demand": f"{target_name} is a customer - customer satisfaction and value delivery matter",
            "regulate": f"{target_name} has regulatory authority - compliance and regulatory risk are important",
            "influence": f"{target_name} can influence outcomes - reputation and persuasion matter",
            "neutral": f"{target_name} is a neutral party - no strong affiliation",
        }
        return relation_knowledge.get(rel_type, f"{target_name} is involved in this situation")

    def query(self, entity_id: str) -> dict:
        """Query knowledge about an entity."""
        if self.graph.has_node(entity_id):
            return dict(self.graph.nodes[entity_id])
        return {}

    def get_neighbors(self, entity_id: str, relation: Optional[str] = None) -> list[dict]:
        """Get neighboring entities, optionally filtered by relation type."""
        neighbors = []
        if not self.graph.has_node(entity_id):
            return neighbors

        for neighbor in self.graph.neighbors(entity_id):
            edge_data = self.graph.get_edge_data(entity_id, neighbor)
            if relation is None or edge_data.get("relation") == relation:
                neighbors.append({
                    "entity_id": neighbor,
                    "relation": edge_data.get("relation"),
                    **self.graph.nodes[neighbor],
                })

        return neighbors

    def validate_action(self, agent: Agent, action: str) -> tuple[bool, str]:
        """Validate if an action is allowed for an agent."""
        constraints = self.get_agent_constraints(agent)

        if action in constraints["forbidden_actions"]:
            return False, f"Action '{action}' is forbidden due to relationship constraints"

        # Check sentiment bounds
        sentiment_belief = next((b for b in agent.beliefs if b.key == "sentiment"), None)
        if sentiment_belief:
            sentiment = float(sentiment_belief.value)
            min_sent, max_sent = constraints["sentiment_bounds"]
            if sentiment < min_sent or sentiment > max_sent:
                return False, f"Current sentiment {sentiment:.2f} is outside allowed range [{min_sent:.2f}, {max_sent:.2f}]"

        return True, "Action is allowed"
