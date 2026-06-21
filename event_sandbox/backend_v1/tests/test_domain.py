"""领域模型单元测试"""

import pytest

from core.domain.common import AgentType, SimulationStatus
from core.domain.agent import Agent, AgentMemory, MemoryEntry
from core.domain.simulation import Simulation, SimulationConfig, SimulationMetrics
from core.domain.event import Event, EventImpact
from core.domain.relation import RelationEdge


class TestAgent:
    def test_create_agent(self):
        agent = Agent(name="测试企业", type=AgentType.COMPANY)
        assert agent.name == "测试企业"
        assert agent.type == AgentType.COMPANY
    def test_memory_system(self):
        memory = AgentMemory(max_short_term=3)
        memory.add_entry(MemoryEntry(round=1, content="记忆1", importance=0.5))
        memory.add_entry(MemoryEntry(round=2, content="记忆2", importance=0.8))
        memory.add_entry(MemoryEntry(round=3, content="记忆3", importance=0.3))
        memory.add_entry(MemoryEntry(round=4, content="记忆4", importance=0.9))

        # 溢出后应归档最重要的 3 条
        assert len(memory.short_term) <= 3
        assert len(memory.long_term) > 0


class TestSimulation:
    def test_create_simulation(self):
        sim = Simulation(name="测试推演", description="测试", rounds=5)
        assert sim.name == "测试推演"
        assert sim.current_round == 0
        assert sim.status == SimulationStatus.PENDING

    def test_relation_operations(self):
        sim = Simulation(name="测试", rounds=5)
        rel = sim.add_or_update_relation("a", "b", "竞争", "A与B竞争激烈", current_round=1)
        assert rel.interaction_count == 1
        assert len(rel.evolution_history) == 1

        # 同一(source, target, relation)会更新
        rel2 = sim.add_or_update_relation("a", "b", "竞争", "A与B转为合作", current_round=2)
        assert rel2.interaction_count == 2
        assert rel2.relation == "竞争"
        assert rel2.description == "A与B转为合作"
        assert len(rel2.evolution_history) == 2

        # 不同 relation 会新建一条边
        rel3 = sim.add_or_update_relation("a", "b", "合作", "A与B合作", current_round=2)
        assert rel3.interaction_count == 1
        assert rel3.relation == "合作"
        assert len(sim.relations) == 2

    def test_get_relations_of(self):
        sim = Simulation(name="测试", rounds=5)
        sim.add_or_update_relation("a", "b", "竞争", "", 1)
        sim.add_or_update_relation("c", "a", "合作", "", 1)
        rels = sim.get_relations_of("a")
        assert len(rels) == 2


class TestEvent:
    def test_event_creation(self):
        event = Event(type="external", description="测试事件", timestamp=123456, round=1)
        assert event.description == "测试事件"
        assert event.round == 1


class TestRelationEdge:
    def test_relation_edge(self):
        rel = RelationEdge(source_id="a", target_id="b", relation="竞争", description="A视B为竞争对手")
        assert rel.source_id == "a"
        assert rel.target_id == "b"
