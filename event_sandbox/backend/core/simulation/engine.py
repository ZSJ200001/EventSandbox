import uuid
import time
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.agent import AgentEngine
from core.event_parser import EventParser
from core.knowledge import KnowledgeGraph
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
    """Core simulation engine that orchestrates the entire simulation."""

    def __init__(
        self,
        llm_client=None,
        knowledge_graph: Optional[KnowledgeGraph] = None,
    ):
        self.agent_engine = AgentEngine(llm_client)
        self.event_parser = EventParser(llm_client)
        self.knowledge = knowledge_graph or KnowledgeGraph()
        self.simulations: dict[str, Simulation] = {}

    def create_simulation(
        self,
        name: str,
        description: str,
        event_text: str,
        config: Optional[SimulationConfig] = None,
    ) -> Simulation:
        """Create a new simulation from event text."""
        if config is None:
            config = SimulationConfig()

        # Parse event and generate agents
        agents, topology, initial_event = self.event_parser.parse(event_text)

        # Create simulation
        simulation = Simulation(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            agents=agents,
            events=[initial_event],
            topology=topology,
            rounds=config.max_rounds,
            current_round=0,
            status=SimulationStatus.PENDING,
            metrics=SimulationMetrics(
                overall_sentiment=0.0,
                market_activity=0.5,
                cooperation_level=0.5,
                conflict_level=0.3,
            ),
        )

        self.simulations[simulation.id] = simulation
        return simulation

    def step(
        self,
        simulation_id: str,
        intervention: Optional[Intervention] = None,
    ) -> tuple[Simulation, list[Event], list[Agent]]:
        """Execute one step of the simulation."""
        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        if simulation.status == SimulationStatus.COMPLETED:
            raise ValueError("Simulation has already completed")

        # Update status to running
        simulation.status = SimulationStatus.RUNNING
        simulation.current_round += 1
        current_round = simulation.current_round

        new_events = []
        updated_agents = []

        # Apply global parameters if this is the first step
        global_params = {}
        if current_round == 1:
            global_params["market_sentiment"] = 0.0
            global_params["economic_outlook"] = "neutral"

        # Handle intervention if present
        if intervention:
            self._apply_intervention(simulation, intervention)
            new_events.append(
                Event(
                    id=str(uuid.uuid4()),
                    type=EventType.INTERVENTION,
                    description=self._describe_intervention(intervention),
                    timestamp=int(time.time() * 1000),
                    round=current_round,
                    involved_agents=[intervention.target] if intervention.target else [],
                    impact=EventImpact(),
                )
            )

        # Each agent decides and acts
        for agent in simulation.agents:
            if agent.status == AgentStatus.INACTIVE:
                continue

            # Get knowledge context
            knowledge_context = self.knowledge.get_knowledge_context(
                agent, simulation.agents
            )

            # Decide action
            result = self.agent_engine.decide_action(
                agent=agent,
                all_agents=simulation.agents,
                recent_events=simulation.events[-5:],
                global_params=global_params,
                knowledge_context=knowledge_context,
            )

            # Apply action result
            event, sentiment_updates = self.agent_engine.apply_action_result(
                agent, result, simulation.agents
            )
            event.round = current_round
            new_events.append(event)

            # Update metrics based on sentiment
            for updated_agent, sentiment_change in sentiment_updates:
                if updated_agent.id not in [a.id for a in updated_agents]:
                    updated_agents.append(updated_agent)

            # Check if action was valid
            valid, _ = self.knowledge.validate_action(agent, result.action)
            if not valid:
                # Skip invalid actions but log them
                event.description = f"[Invalid] {event.description}"

        # Update simulation metrics
        self._update_metrics(simulation)

        # Add new events to simulation
        simulation.events.extend(new_events)

        # Check if simulation should end
        if simulation.current_round >= simulation.rounds:
            simulation.status = SimulationStatus.COMPLETED
            simulation.end_time = int(time.time() * 1000)

        return simulation, new_events, updated_agents

    def _apply_intervention(
        self, simulation: Simulation, intervention: Intervention
    ):
        """Apply an intervention to the simulation."""
        if intervention.type == InterventionType.GLOBAL_PARAM:
            # Update global parameter (would be stored in simulation.extra)
            pass

        elif intervention.type == InterventionType.AGENT_STATE:
            if intervention.target:
                agent = next(
                    (a for a in simulation.agents if a.id == intervention.target), None
                )
                if agent:
                    self.agent_engine.apply_intervention(
                        agent,
                        intervention.type.value,
                        intervention.parameter or "",
                        intervention.value,
                    )

        elif intervention.type == InterventionType.EXTERNAL_EVENT:
            # Add external event
            external_event = Event(
                id=str(uuid.uuid4()),
                type=EventType.EXTERNAL,
                description=str(intervention.value),
                timestamp=int(time.time() * 1000),
                round=simulation.current_round,
                involved_agents=[intervention.target] if intervention.target else [],
                impact=EventImpact(),
            )
            simulation.events.append(external_event)

    def _describe_intervention(self, intervention: Intervention) -> str:
        """Generate a human-readable description of an intervention."""
        if intervention.type == InterventionType.GLOBAL_PARAM:
            return f"Global parameter adjusted: {intervention.parameter} = {intervention.value}"
        elif intervention.type == InterventionType.AGENT_STATE:
            return f"Agent state modified: {intervention.target} - {intervention.parameter} = {intervention.value}"
        elif intervention.type == InterventionType.EXTERNAL_EVENT:
            return f"External event injected: {intervention.value}"
        return "Intervention applied"

    def _update_metrics(self, simulation: Simulation):
        """Update simulation metrics based on current state."""
        total_sentiment = 0.0
        active_agents = 0
        cooperative_count = 0
        conflict_count = 0

        for agent in simulation.agents:
            if agent.status != AgentStatus.INACTIVE:
                active_agents += 1
                sentiment_belief = next(
                    (b for b in agent.beliefs if b.key == "sentiment"), None
                )
                if sentiment_belief:
                    total_sentiment += float(sentiment_belief.value)

                # Count relationships
                for rel in agent.relationships:
                    if rel.type.value in ["cooperative", "supply"]:
                        cooperative_count += 1
                    elif rel.type.value == "competitor":
                        conflict_count += 1

        if active_agents > 0:
            simulation.metrics.overall_sentiment = total_sentiment / active_agents

        total_relations = cooperative_count + conflict_count
        if total_relations > 0:
            simulation.metrics.cooperation_level = cooperative_count / total_relations
            simulation.metrics.conflict_level = conflict_count / total_relations

        # Market activity based on number of events
        simulation.metrics.market_activity = min(
            1.0, len(simulation.events) / (simulation.rounds * len(simulation.agents))
        )

    def get_simulation(self, simulation_id: str) -> Optional[Simulation]:
        """Get a simulation by ID."""
        return self.simulations.get(simulation_id)

    def compare_scenarios(
        self, simulation_id: str, intervention: Intervention
    ) -> dict:
        """Compare simulation with and without an intervention."""
        import copy

        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        # Store original state
        original_events = copy.deepcopy(simulation.events)
        original_metrics = copy.deepcopy(simulation.metrics)

        # Apply intervention and run one step
        self.step(simulation_id, intervention)
        with_intervention = copy.deepcopy(simulation.metrics)

        # Restore original state (simplified - in production would clone entire simulation)
        simulation.events = original_events
        simulation.metrics = original_metrics

        # Calculate comparison
        comparison = []
        for key in ["overall_sentiment", "market_activity", "cooperation_level", "conflict_level"]:
            orig_val = getattr(original_metrics, key)
            new_val = getattr(with_intervention, key)
            diff = new_val - orig_val
            pct = (diff / abs(orig_val)) * 100 if orig_val != 0 else 0

            comparison.append({
                "metric": key,
                "difference": diff,
                "percentage_change": pct,
            })

        return {
            "simulation_id": simulation_id,
            "without_intervention": original_metrics.model_dump(),
            "with_intervention": with_intervention.model_dump(),
            "comparison": comparison,
        }
