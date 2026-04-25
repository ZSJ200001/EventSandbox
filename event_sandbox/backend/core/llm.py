import httpx
import os
import json
from typing import Optional
from pydantic import BaseModel


class LLMConfig(BaseModel):
    api_base: str = "http://101.251.216.47/8411/v1"
    api_key: str = "sk-empty"
    default_model: str = "Qwen3-Coder-Next"
    timeout: float = 120.0


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            config = LLMConfig()
            # Try to load from environment
            config.api_base = os.getenv("LLM_API_BASE", config.api_base)
            config.api_key = os.getenv("LLM_API_KEY", config.api_key)
            config.default_model = os.getenv("DEFAULT_MODEL", config.default_model)

        self.config = config
        self.client = httpx.Client(
            base_url=config.api_base,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout,
        )

    def chat(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send a chat completion request to the LLM API."""
        payload = {
            "model": model or self.config.default_model,
            "messages": [msg.model_dump() for msg in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        response = self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model or self.config.default_model),
            usage=data.get("usage", {}),
        )

    def generate_agent_personality(
        self, agent_type: str, context: str, name: str
    ) -> dict:
        """Generate personality and goals for an agent based on its type and context."""
        system_prompt = """You are an expert at creating realistic agent personas for multi-agent simulations.
Given an agent type and context, generate a detailed personality profile including:
- personality traits (3-5 adjectives)
- core goals (2-4 items)
- key beliefs and values
- behavioral tendencies

Respond in JSON format with these exact keys:
{
    "personality": "comma-separated adjectives",
    "goals": ["goal1", "goal2", ...],
    "beliefs": [{"key": "belief_name", "value": "value", "confidence": 0.0-1.0}],
    "description": "brief description of this agent's role"
}"""

        user_prompt = f"""Agent Type: {agent_type}
Context: {context}
Name: {name}

Generate a realistic personality profile for this agent in the given context."""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        response = self.chat(messages, temperature=0.8)

        try:
            # Try to parse as JSON
            result = json.loads(response.content)
            return result
        except json.JSONDecodeError:
            # If not valid JSON, return a structured response
            return {
                "personality": "neutral, cautious, strategic",
                "goals": ["survive", "grow", "compete"],
                "beliefs": [],
                "description": response.content,
            }

    def decide_action(
        self,
        agent_name: str,
        agent_personality: str,
        agent_goals: list[str],
        current_situation: str,
        available_actions: list[str],
        knowledge_context: str = "",
    ) -> dict:
        """Decide what action an agent should take given the current situation."""
        system_prompt = """You are simulating a realistic decision-making process for an agent.
Based on the agent's personality, goals, and current situation, decide what action to take.

Respond in JSON format with these exact keys:
{
    "action": "the chosen action from available_actions",
    "reasoning": "brief explanation of why this action was chosen",
    "expected_outcome": "what the agent expects to achieve",
    "sentiment_change": -1 to 1 (negative=more negative, positive=more positive),
    "target_agents": ["agent1", "agent2"] if applicable
}"""

        user_prompt = f"""Agent: {agent_name}
Personality: {agent_personality}
Goals: {', '.join(agent_goals)}
Current Situation: {current_situation}
Available Actions: {', '.join(available_actions)}
Knowledge Context: {knowledge_context}

Decide what action this agent should take."""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        response = self.chat(messages, temperature=0.7)

        try:
            result = json.loads(response.content)
            return result
        except json.JSONDecodeError:
            return {
                "action": available_actions[0] if available_actions else "wait",
                "reasoning": response.content[:200],
                "expected_outcome": "unknown",
                "sentiment_change": 0,
                "target_agents": [],
            }

    def parse_event_entities(
        self, event_text: str
    ) -> dict:
        """Parse event text to identify key entities (agents, relationships, etc.)."""
        system_prompt = """You are an expert at analyzing news events and identifying key entities.
Given an event description, identify:
1. Key actors/organizations involved (with their type: company, government, consumer, competitor, etc.)
2. Relationships between actors
3. The nature of the event

Respond in JSON format:
{
    "entities": [
        {"name": "entity_name", "type": "company|government|consumer|competitor|regulator|supplier|individual", "description": "brief description"}
    ],
    "relationships": [
        {"source": "entity1", "target": "entity2", "type": "competitor|cooperative|supply|demand|regulate|influence|neutral", "strength": -1 to 1}
    ],
    "event_summary": "brief summary of what happened"
}"""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"Event: {event_text}"),
        ]

        response = self.chat(messages, temperature=0.3)

        try:
            result = json.loads(response.content)
            return result
        except json.JSONDecodeError:
            return {
                "entities": [],
                "relationships": [],
                "event_summary": event_text[:500],
            }

    def generate_action_description(
        self, agent_name: str, action: str, context: str
    ) -> str:
        """Generate a natural language description of an agent's action."""
        system_prompt = """You are a narrative generator for multi-agent simulations.
Given an agent name, action, and context, generate a brief but vivid description of what happened.
Keep it to 1-2 sentences, as if reporting a news event."""

        user_prompt = f"""Agent: {agent_name}
Action: {action}
Context: {context}

Describe what happened."""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        response = self.chat(messages, temperature=0.7)
        return response.content

    def is_healthy(self) -> bool:
        """Check if the LLM API is reachable."""
        try:
            # Simple models list request to check connectivity
            self.client.get("/models")
            return True
        except Exception:
            return False

    def close(self):
        self.client.close()


# Global client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
