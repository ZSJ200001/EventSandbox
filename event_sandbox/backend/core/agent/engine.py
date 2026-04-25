import uuid
import time
from typing import Optional
import sys
import os

# Add parent directory to path for absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.llm import get_llm_client, LLMMessage
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
    ):
        self.action = action
        self.reasoning = reasoning
        self.expected_outcome = expected_outcome
        self.sentiment_change = sentiment_change
        self.target_agents = target_agents
        self.event_description = event_description


class AgentEngine:
    """Engine for managing agent decision-making and simulation loop."""

    # Action templates by agent type
    ACTION_TEMPLATES = {
        AgentType.COMPANY: [
            "adjust_pricing",
            "launch_promotion",
            "expand_production",
            "reduce_costs",
            "form_alliance",
            "issue_statement",
            "acquire_competitor",
            "invest_in_r&d",
        ],
        AgentType.COMPETITOR: [
            "match_pricing",
            "launch_competing_product",
            "steal_market_share",
            "form_alliance",
            "attack_reputation",
            "innovate",
        ],
        AgentType.CONSUMER: [
            "buy_product",
            "switch_brand",
            "complain",
            "share_experience",
            "boycott",
            "recommend",
        ],
        AgentType.GOVERNMENT: [
            "issue_regulation",
            "launch_investigation",
            " impose_penalty",
            "announce_policy",
            "hold_press_conference",
        ],
        AgentType.REGULATOR: [
            "investigate",
            "issue_warning",
            "impose_fine",
            "announce_policy",
            "hold_hearing",
        ],
        AgentType.SUPPLIER: [
            "adjust_pricing",
            "modify_contract",
            "expand_capacity",
            "restrict_supply",
        ],
        AgentType.ORGANIZATION: [
            "issue_statement",
            "protest",
            "negotiate",
            "lobby",
            "mobilize_members",
        ],
        AgentType.INDIVIDUAL: [
            "express_opinion",
            "take_action",
            "share_information",
            "change_behavior",
        ],
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client or get_llm_client()

    def get_available_actions(self, agent: Agent) -> list[str]:
        """Get available actions for an agent based on its type."""
        return self.ACTION_TEMPLATES.get(agent.type, ["wait", "observe"])

    def build_situation_summary(
        self, agent: Agent, all_agents: list[Agent], recent_events: list[Event]
    ) -> str:
        """Build a text summary of the current situation for an agent."""
        lines = [f"You are {agent.name}."]

        if agent.description:
            lines.append(f"Your role: {agent.description}")
        if agent.personality:
            lines.append(f"Your personality: {agent.personality}")
        if agent.goals:
            lines.append(f"Your goals: {', '.join(agent.goals)}")

        # Current beliefs
        if agent.beliefs:
            lines.append("\nCurrent beliefs:")
            for b in agent.beliefs:
                lines.append(f"  - {b.key}: {b.value} (confidence: {b.confidence:.0%})")

        # Relationships
        if agent.relationships:
            lines.append("\nYour relationships:")
            for rel in agent.relationships:
                target = next((a for a in all_agents if a.id == rel.target_agent_id), None)
                if target:
                    lines.append(f"  - {target.name}: {rel.type} (strength: {rel.strength:.0%})")

        # Recent events
        if recent_events:
            lines.append("\nRecent events:")
            for ev in recent_events[-3:]:
                lines.append(f"  - Round {ev.round}: {ev.description}")

        return "\n".join(lines)

    def decide_action(
        self,
        agent: Agent,
        all_agents: list[Agent],
        recent_events: list[Event],
        global_params: dict,
        knowledge_context: str = "",
    ) -> ActionResult:
        """Decide what action an agent should take this round."""
        situation = self.build_situation_summary(agent, all_agents, recent_events)
        available_actions = self.get_available_actions(agent)

        # Add global parameters context
        if global_params:
            param_str = ", ".join([f"{k}: {v}" for k, v in global_params.items()])
            situation += f"\n\nGlobal environment: {param_str}"

        decision = self.llm.decide_action(
            agent_name=agent.name,
            agent_personality=agent.personality,
            agent_goals=agent.goals,
            current_situation=situation,
            available_actions=available_actions,
            knowledge_context=knowledge_context,
        )

        action = decision.get("action", "wait")
        if action not in available_actions:
            action = available_actions[0]

        # Generate event description
        context = f"Current round: {len(recent_events) + 1}"
        event_desc = self.llm.generate_action_description(
            agent_name=agent.name, action=action, context=context
        )

        return ActionResult(
            action=action,
            reasoning=decision.get("reasoning", ""),
            expected_outcome=decision.get("expected_outcome", ""),
            sentiment_change=decision.get("sentiment_change", 0),
            target_agents=decision.get("target_agents", []),
            event_description=event_desc,
        )

    def apply_action_result(
        self,
        agent: Agent,
        result: ActionResult,
        all_agents: list[Agent],
    ) -> tuple[Event, list[tuple[Agent, float]]]:
        """Apply an action result to update agent state and create an event."""
        # Create event
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.ACTION,
            description=result.event_description,
            timestamp=int(time.time() * 1000),
            round=0,  # Will be set by simulation engine
            involved_agents=[agent.id] + result.target_agents,
            impact=EventImpact(
                affected_agents=result.target_agents,
                sentiment_change={agent.id: result.sentiment_change},
            ),
        )

        # Update agent sentiment/beliefs
        sentiment_updates: list[tuple[Agent, float]] = []
        for b in agent.beliefs:
            if b.key == "sentiment":
                b.value = float(b.value) + result.sentiment_change
                b.confidence = min(1.0, b.confidence + 0.1)
                sentiment_updates.append((agent, result.sentiment_change))

        # Update relationships
        for rel in agent.relationships:
            if rel.target_agent_id in result.target_agents:
                # Adjust relationship strength based on sentiment
                rel.strength += result.sentiment_change * 0.1
                rel.strength = max(-1, min(1, rel.strength))

        # Propagate sentiment to target agents
        for target_id in result.target_agents:
            target = next((a for a in all_agents if a.id == target_id), None)
            if target:
                sentiment_updates.append((target, result.sentiment_change * 0.3))

        return event, sentiment_updates

    def apply_intervention(
        self,
        agent: Agent,
        intervention_type: str,
        parameter: str,
        value: str | int | float | bool,
    ) -> Agent:
        """Apply an intervention to modify agent state."""
        agent.status = AgentStatus.INTERVENED

        if intervention_type == "agent_state":
            if parameter == "sentiment":
                for b in agent.beliefs:
                    if b.key == "sentiment":
                        b.value = float(value)
                        b.confidence = 1.0
                        break
            elif parameter == "belief":
                # Value should be a dict with key and value
                if isinstance(value, dict):
                    agent.beliefs.append(
                        Belief(
                            key=value.get("key", "unknown"),
                            value=value.get("value", ""),
                            confidence=0.9,
                        )
                    )
        elif intervention_type == "external_event":
            # Add new goal or constraint
            if isinstance(value, str):
                agent.goals.append(f"应对外部事件: {value}")

        return agent
