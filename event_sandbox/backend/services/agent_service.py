import uuid
import time
from typing import Optional
from core.agent import AgentEngine
from core.knowledge import KnowledgeGraph


class AgentService:
    """Service layer for agent operations."""

    def __init__(self):
        self.knowledge_graph = KnowledgeGraph()

    def create_agent(
        self,
        name: str,
        agent_type: str,
        personality: str = "",
        goals: list[str] = None,
        description: str = "",
    ) -> dict:
        """Create a new agent with basic configuration."""
        from core.llm import get_llm_client

        llm = get_llm_client()

        # Generate personality if not provided
        if not personality:
            result = llm.generate_agent_personality(agent_type, description, name)
            personality = result.get("personality", "neutral")

        if goals is None:
            goals = ["survive", "grow"]

        agent = {
            "id": str(uuid.uuid4()),
            "name": name,
            "type": agent_type,
            "personality": personality,
            "goals": goals,
            "description": description,
            "beliefs": [{"key": "sentiment", "value": 0.0, "confidence": 0.5}],
            "relationships": [],
            "status": "active",
        }

        return agent

    def get_agent_context(self, agent: dict, all_agents: list[dict]) -> str:
        """Get knowledge context for an agent."""
        return self.knowledge_graph.get_knowledge_context(agent, all_agents)

    def validate_agent_action(self, agent: dict, action: str) -> tuple[bool, str]:
        """Validate if an agent can take a specific action."""
        return self.knowledge_graph.validate_action(agent, action)


# Global service instance
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
