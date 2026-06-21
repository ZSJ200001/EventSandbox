"""报告生成引擎测试"""

import pytest

from core.domain.agent import Agent
from core.domain.common import AgentType
from core.domain.simulation import Simulation, SimulationConfig, TimelineEntry
from engines.report_engine import ReportEngine
from infrastructure.llm.schemas import LLMResponse


def _make_simulation() -> Simulation:
    """构造一个用于测试的 Simulation 对象"""
    agent_a = Agent(
        id="a0000001",
        name="德国队",
        type=AgentType.GOVERNMENT,
        description="足球强队",
        personality="强势、进攻",
        goals=["赢得比赛"],
        is_actionable=True,
        action_count=3,
    )
    agent_b = Agent(
        id="a0000002",
        name="库拉索队",
        type=AgentType.GOVERNMENT,
        description="弱旅",
        personality="顽强防守",
        goals=["争取平局"],
        is_actionable=True,
        action_count=2,
    )
    agent_c = Agent(
        id="a0000003",
        name="世界杯组委会",
        type=AgentType.ORGANIZATION,
        description="赛事组织者",
        is_actionable=False,
        action_count=0,
    )

    return Simulation(
        id="sim00001",
        name="足球比赛推演",
        description="测试推演",
        agents=[agent_a, agent_b, agent_c],
        rounds=5,
        current_round=2,
        config=SimulationConfig(main_line="测试主线"),
    )


class TestHelperMethods:
    """辅助方法单元测试"""

    def test_resolve_agent_name(self):
        """Agent 名称解析应同时支持 ID 和名称"""
        sim = _make_simulation()
        engine = ReportEngine(llm_client=None, repository=None)

        assert engine._resolve_agent_name(sim, "a0000001") == "德国队"
        assert engine._resolve_agent_name(sim, "库拉索队") == "库拉索队"
        assert engine._resolve_agent_name(sim, "不存在") == "不存在"
        assert engine._resolve_agent_name(sim, "") == "未知"

    def test_build_agent_actions_objective(self):
        """客观行动记录应排除无外部影响的观望行动"""
        sim = _make_simulation()
        sim.timeline = [
            TimelineEntry(
                round=1,
                type="agent_action",
                actor="德国队",
                action="观望/不行动",
                details={"sentiment_change": 0.0},
            ),
            TimelineEntry(
                round=2,
                type="agent_action",
                actor="德国队",
                action="进攻",
                details={
                    "target_agents": ["库拉索队"],
                    "relation_updates": [
                        {"source_id": "德国队", "target_id": "库拉索队", "relation": "压制", "polarity": "negative"}
                    ],
                },
            ),
        ]

        engine = ReportEngine(llm_client=None, repository=None)
        records = engine._build_agent_actions_objective("德国队", sim)

        assert len(records) == 1
        assert records[0]["round"] == 2
        assert records[0]["action"] == "进攻"

    def test_build_timeline_facts(self):
        """时间线事实应按回合分组，并包含关系变化"""
        sim = _make_simulation()
        sim.timeline = [
            TimelineEntry(
                round=1,
                type="external_event",
                actor="系统",
                description="比赛开始",
            ),
            TimelineEntry(
                round=2,
                type="agent_action",
                actor="德国队",
                action="攻入一球",
                details={
                    "target_agents": ["库拉索队"],
                    "relation_updates": [
                        {"source_id": "德国队", "target_id": "库拉索队", "relation": "压制", "polarity": "negative"}
                    ],
                },
                before={"relation": "对抗", "polarity": "neutral"},
                after={"relation": "压制", "polarity": "negative"},
            ),
        ]

        engine = ReportEngine(llm_client=None, repository=None)
        facts = engine._build_timeline_facts(sim)

        assert len(facts) == 2
        assert facts[0]["round"] == 1
        assert "比赛开始" in facts[0]["facts"][0]
        assert facts[1]["round"] == 2
        assert "德国队" in facts[1]["facts"][0]
        assert "库拉索队" in facts[1]["facts"][0]


@pytest.mark.asyncio
class TestReportGenerationIntegration:
    """报告生成集成测试（通过 monkeypatch 模拟 LLM，无需真实网络）"""

    async def test_generate_report_structure(self, report_engine):
        """端到端验证报告结构完整（无关键点、无局势脉络）"""
        sim = _make_simulation()
        sim.timeline = [
            TimelineEntry(
                round=1,
                type="external_event",
                actor="系统",
                description="比赛开始",
            ),
            TimelineEntry(
                round=2,
                type="agent_action",
                actor="德国队",
                action="攻入一球",
                details={
                    "target_agents": ["库拉索队"],
                    "relation_updates": [
                        {"source_id": "德国队", "target_id": "库拉索队", "relation": "压制", "polarity": "negative"}
                    ],
                },
                before={"relation": "对抗", "polarity": "neutral"},
                after={"relation": "压制", "polarity": "negative"},
            ),
        ]

        async def fake_chat(*args, **kwargs):
            return LLMResponse(content="测试内容", model="test")

        report_engine.llm.chat = fake_chat

        report = await report_engine.generate(sim)

        assert report.simulation_id == sim.id
        assert report.title
        assert len(report.agent_summaries) > 0
        assert report.overall_summary == "测试内容"
        assert report.conclusion == "测试内容"
        assert report.full_report
        assert "## 一、核心 Agent 行为分析" in report.full_report
        assert "## 二、整体局势分析" in report.full_report
        assert "## 三、结论" in report.full_report
        assert "关键点" not in report.full_report
        assert "局势演变脉络" not in report.full_report
        assert sim.report

    async def test_generate_report_conclusion_focuses_main_line(self, report_engine):
        """结论 Prompt 中应包含推演主线"""
        sim = _make_simulation()
        sim.config.main_line = "谁会赢得比赛？"
        sim.timeline = [
            TimelineEntry(
                round=2,
                type="agent_action",
                actor="德国队",
                action="攻入一球",
                details={
                    "target_agents": ["库拉索队"],
                    "relation_updates": [
                        {"source_id": "德国队", "target_id": "库拉索队", "relation": "压制", "polarity": "negative"}
                    ],
                },
                before={"relation": "对抗", "polarity": "neutral"},
                after={"relation": "压制", "polarity": "negative"},
            ),
        ]

        captured_prompts = []

        async def fake_chat(*args, **kwargs):
            messages = kwargs.get("messages") or (args[0] if args else [])
            if messages:
                captured_prompts.append(messages[-1].content)
            return LLMResponse(content="测试结论", model="test")

        report_engine.llm.chat = fake_chat

        await report_engine.generate(sim)

        # 找到结论调用的 prompt（最后一个）
        conclusion_prompt = captured_prompts[-1]
        assert "推演主线" in conclusion_prompt
        assert "谁会赢得比赛？" in conclusion_prompt
