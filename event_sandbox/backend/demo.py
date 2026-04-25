#!/usr/bin/env python3
"""
EventSandbox Demo Script
Demonstrates the core functionality of the EventSandbox system.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import SimulationEngine, get_llm_client


def print_separator():
    print("=" * 60)


def print_agents(agents):
    """Print agent information."""
    print("\n--- Agents ---")
    for agent in agents:
        sentiment = next((b.value for b in agent.beliefs if b.key == "sentiment"), 0)
        print(f"\n[{agent.type}] {agent.name}")
        print(f"  Personality: {agent.personality}")
        print(f"  Goals: {', '.join(agent.goals)}")
        print(f"  Status: {agent.status}")
        print(f"  Sentiment: {float(sentiment):.2f}")
        print(f"  Relationships: {len(agent.relationships)}")


def print_topology(topology):
    """Print topology information."""
    print("\n--- Topology ---")
    print(f"Nodes: {len(topology.nodes)}")
    print(f"Edges: {len(topology.edges)}")

    for node in topology.nodes[:5]:
        print(f"  - {node.label} ({node.type})")

    for edge in topology.edges[:5]:
        print(f"  - {edge.source} --[{edge.relation}]--> {edge.target}")


def print_metrics(metrics):
    """Print simulation metrics."""
    print("\n--- Metrics ---")
    print(f"  Overall Sentiment: {metrics.overall_sentiment:.3f}")
    print(f"  Market Activity: {metrics.market_activity:.3f}")
    print(f"  Cooperation Level: {metrics.cooperation_level:.3f}")
    print(f"  Conflict Level: {metrics.conflict_level:.3f}")


def print_recent_events(events, n=5):
    """Print recent events."""
    print(f"\n--- Recent Events (last {n}) ---")
    for event in events[-n:]:
        print(f"  [Round {event.round}] {event.type}: {event.description[:60]}...")


async def run_demo():
    """Run the demo simulation."""
    print_separator()
    print("EventSandbox Demo - 奶茶涨价事件推演")
    print_separator()

    # Check LLM connection
    print("\nChecking LLM connection...")
    llm = get_llm_client()
    if llm.is_healthy():
        print("LLM API is connected and ready!")
    else:
        print("Warning: LLM API is not reachable. Using fallback mode.")

    # Create simulation engine
    engine = SimulationEngine()

    # Create simulation
    print("\n" + "-" * 40)
    print("Creating simulation...")
    event_text = "XX奶茶招牌产品涨价3元"

    simulation = engine.create_simulation(
        name="奶茶涨价推演",
        description="模拟奶茶品牌涨价后的市场反应",
        event_text=event_text,
    )

    print(f"Simulation ID: {simulation.id}")
    print(f"Number of agents: {len(simulation.agents)}")
    print_agents(simulation.agents)
    print_topology(simulation.topology)

    # Run a few simulation steps
    print("\n" + "-" * 40)
    print("Running simulation steps...")

    for i in range(3):
        print(f"\n--- Step {i + 1} ---")
        simulation, new_events, updated_agents = engine.step(simulation.id)

        print(f"Current round: {simulation.current_round}")
        print(f"Status: {simulation.status}")
        print_metrics(simulation.metrics)

        if new_events:
            print(f"\nNew events this round:")
            for event in new_events:
                print(f"  - [{event.type}] {event.description[:70]}...")

    # Test intervention
    print("\n" + "-" * 40)
    print("Testing intervention...")

    from models.entities import Intervention, InterventionType

    intervention = Intervention(
        id="test_intervention",
        type=InterventionType.EXTERNAL_EVENT,
        target=None,
        parameter=None,
        value="监管部门约谈奶茶品牌",
        timestamp=0,
        round=simulation.current_round,
    )

    simulation, new_events, _ = engine.step(simulation.id, intervention)

    print(f"After intervention:")
    print(f"  Current round: {simulation.current_round}")
    print_metrics(simulation.metrics)

    # Test scenario comparison
    print("\n" + "-" * 40)
    print("Testing scenario comparison...")

    comparison = engine.compare_scenarios(
        simulation.id,
        Intervention(
            id="compare_intervention",
            type=InterventionType.AGENT_STATE,
            target=simulation.agents[0].id if simulation.agents else None,
            parameter="sentiment",
            value=0.5,
            timestamp=0,
            round=0,
        )
    )

    print("Comparison result:")
    for item in comparison.get("comparison", []):
        print(f"  {item['metric']}: {item['difference']:+.3f} ({item['percentage_change']:+.1f}%)")

    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)

    return simulation


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_demo())
