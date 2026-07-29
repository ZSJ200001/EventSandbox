"""推演报告生成引擎

三层生成结构：
1. 逐 Agent 过程分析（并发 LLM 调用）
2. 整体局势描述（单次 LLM 调用）
3. 结论（单次 LLM 调用，紧扣推演主线）
"""

import asyncio
import logging
from typing import Optional

from core.domain.simulation import Simulation
from core.domain.agent import Agent
from infrastructure.llm.client import AsyncLLMClient
from infrastructure.llm.schemas import LLMMessage
from infrastructure.llm.prompts import (
    SYS_GENERATE_BASELINE_REPORT,
    SYS_GENERATE_OVERALL_SUMMARY,
    SYS_ANALYZE_AGENT_REPORT,
    SYS_GENERATE_CONCLUSION,
)
from schemas.report_responses import AgentSummary, GenerateReportResponse

logger = logging.getLogger(__name__)


class ReportEngine:
    """报告生成引擎"""

    def __init__(self, llm_client: AsyncLLMClient, repository=None):
        self.llm = llm_client
        self.repo = repository
        logger.info("[ReportEngine] 初始化完成")

    # ============== 工具方法 ==============

    def _resolve_agent_name(self, simulation: Simulation, identifier: str) -> str:
        """将 ID 或名称解析为 Agent 名称，解析失败返回原字符串"""
        if not identifier:
            return "未知"
        agent = simulation.get_agent_by_id_or_name(identifier)
        return agent.name if agent else identifier

    def _resolve_target_from_action(self, entry) -> str:
        """从 agent_action 条目中解析目标名称/ID"""
        details = entry.details or {}
        relation_changes = details.get("relation_changes", []) or []
        if relation_changes and isinstance(relation_changes, list):
            rc = relation_changes[0]
            target = rc.get("target_name") or rc.get("target_id", "")
            if target:
                return target
        target_agents = details.get("target_agents", []) or []
        if target_agents:
            return target_agents[0]
        return "未知"

    def _build_agent_actions_objective(self, agent_name: str, simulation: Simulation) -> list[dict]:
        """提取某个 Agent 的客观行动记录（不含情绪指标）"""
        records = []
        for entry in simulation.timeline:
            if entry.type != "agent_action" or entry.actor != agent_name:
                continue
            details = entry.details or {}
            action = entry.action or "观望/不行动"
            relation_changes = details.get("relation_changes", []) or []
            target_agents = details.get("target_agents", []) or []
            # 跳过无外部影响的观望行动
            if action in ("观望", "不行动", "观望/不行动") and not relation_changes and not target_agents:
                continue
            records.append({
                "round": entry.round,
                "action": action,
                "targets": target_agents,
                "relation_changes": relation_changes,
            })
        return records

    def _build_timeline_facts(self, simulation: Simulation) -> list[dict]:
        """按回合分组整理 timeline 中的客观事实"""
        facts_by_round: dict[int, list[str]] = {}
        for entry in sorted(simulation.timeline, key=lambda x: x.round):
            if entry.type == "external_event":
                text = f"外部事件：{entry.description}"
            elif entry.type == "agent_added":
                text = f"新增实体：{entry.description}"
            elif entry.type == "world_event":
                text = f"事件：{entry.action}"
                if entry.description:
                    text += f"：{entry.description}"
            elif entry.type == "agent_action":
                details = entry.details or {}
                relation_changes = details.get("relation_changes", []) or []
                # 优先使用 details 中保存的 relation_changes 列表，可完整记录多条关系变化
                if relation_changes:
                    for rc in relation_changes:
                        before_r = rc.get("before_relation", "")
                        after_r = rc.get("after_relation", "")
                        before_p = rc.get("before_polarity", "")
                        after_p = rc.get("after_polarity", "")
                        # 兼容旧格式
                        if not before_r and not after_r:
                            before_r = rc.get("relation", "")
                            after_r = rc.get("relation", "")
                        if (before_r, before_p) == (after_r, after_p):
                            continue
                        source = entry.actor
                        target_raw = rc.get("target_name") or rc.get("target_id", "")
                        target = self._resolve_agent_name(simulation, target_raw)
                        relation_label = after_r or before_r or "关系"
                        before_text = f"{before_r or '-'}" + (f"（{before_p}）" if before_p else "")
                        after_text = f"{after_r or '-'}" + (f"（{after_p}）" if after_p else "")
                        text = f"关系变化：{source} 对 {target} 的「{relation_label}」从 {before_text} 变为 {after_text}"
                        facts_by_round.setdefault(entry.round, []).append(text)
                    continue
                # 兜底：使用条目前后的整体关系快照
                if entry.before and entry.after:
                    before_r = entry.before.get("relation", "")
                    after_r = entry.after.get("relation", "")
                    before_p = entry.before.get("polarity", "")
                    after_p = entry.after.get("polarity", "")
                    if (before_r, before_p) == (after_r, after_p):
                        continue
                    source = entry.actor
                    target = self._resolve_agent_name(
                        simulation, self._resolve_target_from_action(entry)
                    )
                    relation_label = after_r or before_r or "关系"
                    before_text = f"{before_r or '-'}" + (f"（{before_p}）" if before_p else "")
                    after_text = f"{after_r or '-'}" + (f"（{after_p}）" if after_p else "")
                    text = f"关系变化：{source} 对 {target} 的「{relation_label}」从 {before_text} 变为 {after_text}"
                else:
                    continue
            else:
                continue
            facts_by_round.setdefault(entry.round, []).append(text)

        return [
            {"round": r, "facts": facts_by_round[r]}
            for r in sorted(facts_by_round)
        ]

    def _build_world_state_facts(self, simulation: Simulation) -> list[dict]:
        """按回合整理世界状态变化"""
        history = simulation.world_state_history
        if len(history) <= 1:
            return []

        facts = []
        prev_state = history[0].get("state", {}) if history else {}
        for item in history[1:]:
            round_num = item.get("round", 0)
            state = item.get("state", {})
            changes = []
            for key, value in state.items():
                if prev_state.get(key) != value:
                    changes.append(f"{key}: {prev_state.get(key, '-')} -> {value}")
            if changes:
                facts.append({"round": round_num, "changes": changes})
            prev_state = state
        return facts

    def _build_world_events_facts(self, simulation: Simulation) -> list[dict]:
        """按回合整理离散世界事件"""
        if not simulation.world_events_history:
            return []

        facts_by_round: dict[int, list[str]] = {}
        for evt in simulation.world_events_history:
            text = f"{evt.type}"
            if evt.actor:
                text += f"（{evt.actor}）"
            if evt.description:
                text += f"：{evt.description}"
            facts_by_round.setdefault(evt.round, []).append(text)

        return [
            {"round": r, "events": facts_by_round[r]}
            for r in sorted(facts_by_round)
        ]

    def _get_initial_event_description(self, simulation: Simulation) -> str:
        """获取初始事件描述"""
        initial_events = [e for e in simulation.events if e.type.value == "external"]
        if initial_events:
            return initial_events[0].description or ""
        return ""

    # ============== 第一层：逐 Agent 过程分析（并发 LLM） ==============

    async def _analyze_agent(self, agent: Agent, simulation: Simulation) -> AgentSummary:
        """为单个 Agent 生成行为小结"""
        records = self._build_agent_actions_objective(agent.name, simulation)

        if not records:
            return AgentSummary(agent_name=agent.name, summary=f"{agent.name} 在推演中未采取显著行动。")

        lines = []
        for rec in records:
            rel_changes = []
            for ru in rec.get("relation_changes", []):
                target_raw = ru.get("target_name") or ru.get("target_id", "")
                target_name = self._resolve_agent_name(simulation, target_raw)
                relation = ru.get("after_relation") or ru.get("relation", "")
                polarity = ru.get("after_polarity") or ru.get("polarity", "")
                rel_changes.append(f"{relation}→{target_name}({polarity})")
            rel_text = f" 关系变化：{', '.join(rel_changes)}" if rel_changes else ""
            target_text = f" 对象：{', '.join(rec['targets'])}" if rec.get("targets") else ""
            lines.append(f"- 回合{rec['round']}: {rec['action']}{target_text}{rel_text}")

        timeline_text = "\n".join(lines)

        # 该 Agent 作为 source 或 target 的关系变化（来自 timeline 中所有行动的 relation_changes）
        agent_relation_changes = []
        for entry in simulation.timeline:
            if entry.type != "agent_action":
                continue
            details = entry.details or {}
            relation_changes = details.get("relation_changes", []) or []
            if not relation_changes:
                continue
            for ru in relation_changes:
                # source 一般是当前行动者；兼容旧格式中的 source_id
                source_raw = ru.get("source_name") or ru.get("source_id") or entry.actor
                target_raw = ru.get("target_name") or ru.get("target_id", "")
                source_name = self._resolve_agent_name(simulation, source_raw)
                target_name = self._resolve_agent_name(simulation, target_raw)
                if agent.name not in (source_name, target_name):
                    continue
                relation = ru.get("after_relation") or ru.get("relation", "")
                polarity = ru.get("after_polarity") or ru.get("polarity", "")
                agent_relation_changes.append(
                    f"- {source_name} → {target_name}: {relation} ({polarity})"
                )
        relation_text = "\n".join(agent_relation_changes) if agent_relation_changes else "无"

        prompt = f"""【角色信息】
- 名称: {agent.name}
- 类型: {agent.type.value if hasattr(agent.type, 'value') else str(agent.type)}
- 性格: {agent.personality or '未知'}
- 描述: {agent.description or '无'}
- 目标: {', '.join(agent.goals) if agent.goals else '无'}

【推演主线】
{simulation.config.main_line or '无'}

【行动记录（按回合）】
{timeline_text}

【关系演变】
{relation_text}
"""

        try:
            messages = [
                LLMMessage(role="system", content=SYS_ANALYZE_AGENT_REPORT),
                LLMMessage(role="user", content=prompt),
            ]
            response = await self.llm.chat(messages=messages, temperature=0.3, max_tokens=1024)
            return AgentSummary(agent_name=agent.name, summary=response.content.strip())
        except Exception as e:
            logger.warning("[ReportEngine] Agent %s 分析失败: %s", agent.name, e)
            return AgentSummary(agent_name=agent.name, summary=f"{agent.name} 的行为分析生成失败。")

    async def _analyze_all_agents(self, simulation: Simulation) -> list[AgentSummary]:
        """并发分析核心 Agent（有实际行动的 Top 5）"""
        actionable_agents = [a for a in simulation.agents if a.is_actionable]

        # 只保留至少有一次非观望行动的 Agent
        agents_with_actions = []
        for agent in actionable_agents:
            records = self._build_agent_actions_objective(agent.name, simulation)
            if records:
                agents_with_actions.append(agent)

        sorted_agents = sorted(agents_with_actions, key=lambda a: a.action_count, reverse=True)[:5]

        if not sorted_agents:
            return []

        tasks = [self._analyze_agent(agent, simulation) for agent in sorted_agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summaries = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("[ReportEngine] Agent 分析任务异常: %s", r)
                continue
            summaries.append(r)
        return summaries

    # ============== 第二层：整体局势描述（单次 LLM） ==============

    async def _generate_overall_summary(
        self, simulation: Simulation, timeline_facts: list[dict]
    ) -> str:
        """生成整体局势描述（按回合顺序的客观事实描述）"""
        fact_lines = []
        for item in timeline_facts:
            round_facts = [f"- {f}" for f in item["facts"]]
            fact_lines.append(f"回合{item['round']}:\n" + "\n".join(round_facts))

        world_state_facts = self._build_world_state_facts(simulation)
        world_state_lines = []
        for item in world_state_facts:
            changes = [f"- {c}" for c in item["changes"]]
            world_state_lines.append(f"回合{item['round']}世界状态变化:\n" + "\n".join(changes))

        world_events_facts = self._build_world_events_facts(simulation)
        world_events_lines = []
        for item in world_events_facts:
            events = [f"- {e}" for e in item["events"]]
            world_events_lines.append(f"回合{item['round']}离散事件:\n" + "\n".join(events))

        prompt = f"""【推演概况】
- 总回合: {simulation.current_round}
- Agent 数: {len(simulation.agents)}
- 事件数: {len(simulation.events)}
- 推演主线: {simulation.config.main_line or '无'}

【关键事实时间线】
{chr(10).join(fact_lines) if fact_lines else '无'}

【世界状态变化】
{chr(10).join(world_state_lines) if world_state_lines else '无'}

【离散事件】
{chr(10).join(world_events_lines) if world_events_lines else '无'}
"""

        try:
            messages = [
                LLMMessage(role="system", content=SYS_GENERATE_OVERALL_SUMMARY),
                LLMMessage(role="user", content=prompt),
            ]
            response = await self.llm.chat(messages=messages, temperature=0.3, max_tokens=2048)
            return response.content.strip()
        except Exception as e:
            logger.warning("[ReportEngine] 整体总结生成失败: %s", e)
            return "整体局势描述生成失败。"

    # ============== 第三层：结论（单次 LLM，紧扣推演主线） ==============

    async def _generate_conclusion(
        self, simulation: Simulation, overall_summary: str, timeline_facts: list[dict],
        agent_summaries: list[AgentSummary],
    ) -> str:
        """生成结论：综合 Agent 行为分析、局势描述和事实，直接回答推演主线"""
        fact_lines = []
        for item in timeline_facts:
            for f in item["facts"]:
                fact_lines.append(f"- 回合{item['round']}: {f}")

        initial_event = self._get_initial_event_description(simulation)

        final_state_lines = []
        if simulation.world_state:
            final_state_lines = [f"- {k}: {v}" for k, v in simulation.world_state.items()]

        agent_analysis_lines = []
        for s in agent_summaries:
            agent_analysis_lines.append(f"### {s.agent_name}\n{s.summary}")

        prompt = f"""【推演主线】
{simulation.config.main_line or '无'}

【初始事件】
{initial_event or '无'}

【最终世界状态】
{chr(10).join(final_state_lines) if final_state_lines else '无'}

【各角色行为分析】
{chr(10).join(agent_analysis_lines) if agent_analysis_lines else '无'}

【整体局势描述】
{overall_summary}

【关键事实】
{chr(10).join(fact_lines) if fact_lines else '无'}
"""

        try:
            messages = [
                LLMMessage(role="system", content=SYS_GENERATE_CONCLUSION),
                LLMMessage(role="user", content=prompt),
            ]
            response = await self.llm.chat(messages=messages, temperature=0.3, max_tokens=1024)
            return response.content.strip()
        except Exception as e:
            logger.warning("[ReportEngine] 结论生成失败: %s", e)
            return "结论生成失败。"

    # ============== 公开入口 ==============

    async def generate(
        self, simulation: Simulation, progress_callback: Optional[callable] = None
    ) -> GenerateReportResponse:
        """生成完整推演报告"""
        logger.info("[ReportEngine] 开始生成报告, sim=%s", simulation.id)

        def _notify(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        timeline_facts = self._build_timeline_facts(simulation)

        # 第一层：逐 Agent 分析（并发）
        _notify(f"正在分析 Agent 行为（共 {len(simulation.agents)} 个）...")
        agent_summaries = await self._analyze_all_agents(simulation)
        logger.info("[ReportEngine] Agent 分析完成: %d 个", len(agent_summaries))

        # 第二层：整体总结
        _notify("正在生成整体局势描述...")
        overall_summary = await self._generate_overall_summary(simulation, timeline_facts)
        logger.info("[ReportEngine] 整体总结完成")

        # 第三层：结论（综合 Agent 分析、局势描述和事实）
        _notify("正在撰写结论（对接推演主线）...")
        conclusion = await self._generate_conclusion(simulation, overall_summary, timeline_facts, agent_summaries)
        logger.info("[ReportEngine] 结论生成完成")

        # 组装完整报告 Markdown
        full_report = self._build_full_report(
            simulation, agent_summaries, overall_summary, conclusion
        )

        report_data = GenerateReportResponse(
            simulation_id=simulation.id,
            title=f"{simulation.name} 推演分析报告",
            agent_summaries=agent_summaries,
            overall_summary=overall_summary,
            conclusion=conclusion,
            full_report=full_report,
        )

        # 保存到 simulation 并持久化
        simulation.report = report_data.model_dump()
        if self.repo:
            await self.repo.save(simulation)
            logger.info("[ReportEngine] 报告已持久化, sim=%s", simulation.id)

        return report_data

    def _build_full_report(
        self,
        simulation: Simulation,
        agent_summaries: list[AgentSummary],
        overall_summary: str,
        conclusion: str,
    ) -> str:
        """组装 Markdown 完整报告"""
        lines = [
            f"# {simulation.name} 推演分析报告",
            "",
            f"**推演回合**: {simulation.current_round} / {simulation.rounds}",
            f"**Agent 数**: {len(simulation.agents)}",
            f"**事件数**: {len(simulation.events)}",
            f"**推演主线**: {simulation.config.main_line or '无'}",
            "",
            "## 一、核心 Agent 行为分析",
            "",
        ]
        for s in agent_summaries:
            lines.append(f"### {s.agent_name}")
            lines.append(s.summary)
            lines.append("")

        lines.extend([
            "## 二、整体局势分析",
            "",
            overall_summary,
            "",
            "## 三、结论",
            "",
            conclusion,
            "",
        ])

        return "\n".join(lines)


class BaselineReportEngine:
    """基线报告生成引擎（纯 LLM 线性推演，无多 Agent 交互）"""

    def __init__(self, llm_client: AsyncLLMClient, repository=None):
        self.llm = llm_client
        self.repo = repository
        logger.info("[BaselineReportEngine] 初始化完成")

    async def generate(
        self, simulation: Simulation, progress_callback: Optional[callable] = None
    ) -> GenerateReportResponse:
        """生成基线报告：基于初始输入，让 LLM 线性推演已发生的回合"""
        logger.info("[BaselineReportEngine] 开始生成基线报告, sim=%s", simulation.id)

        def _notify(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        _notify("正在分析初始事件和实体信息...")
        # 构造用户 Prompt
        prompt = self._build_prompt(simulation)

        _notify("正在调用 LLM 生成基线报告...")
        # 调用 LLM
        messages = [
            LLMMessage(role="system", content=SYS_GENERATE_BASELINE_REPORT),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm.chat(messages=messages, temperature=0.5, max_tokens=4096)
            raw = response.content.strip()
            parsed = self.llm._parse_json(raw, {})
        except Exception as e:
            logger.warning("[BaselineReportEngine] LLM 返回解析失败: %s", e)
            parsed = {}

        # 解析为结构化数据
        agent_summaries = []
        for s in parsed.get("agent_summaries", []):
            try:
                agent_summaries.append(AgentSummary.model_validate(s))
            except Exception:
                continue

        overall_summary = parsed.get("overall_summary", "")
        conclusion = parsed.get("conclusion", "")

        # 组装完整报告 Markdown
        full_report = self._build_full_report(
            simulation, agent_summaries, overall_summary, conclusion
        )

        report_data = GenerateReportResponse(
            simulation_id=simulation.id,
            title=f"{simulation.name} 基线预测报告（纯 LLM）",
            agent_summaries=agent_summaries,
            overall_summary=overall_summary,
            conclusion=conclusion,
            full_report=full_report,
        )

        # 保存到 simulation 并持久化
        simulation.baseline_report = report_data.model_dump()
        if self.repo:
            await self.repo.save(simulation)
            logger.info("[BaselineReportEngine] 基线报告已持久化, sim=%s", simulation.id)

        return report_data

    def _build_prompt(self, simulation: Simulation) -> str:
        """构造基线报告用户 Prompt"""
        lines = [
            f"推演背景：{simulation.description or '无'}",
            f"推演主线：{simulation.config.main_line or '无'}",
            f"已推进回合数：{simulation.current_round}",
            f"总设定回合数：{simulation.rounds}",
        ]

        # 初始事件描述（从 events 中取第一个外部事件）
        initial_events = [e for e in simulation.events if e.type.value == "external"]
        if initial_events:
            lines.append(f"初始事件描述：{initial_events[0].description or '无'}")

        # 推演涉及实体列表（名称和类型）
        if simulation.agents:
            agent_lines = [f"- {a.name}（{a.type.value if hasattr(a.type, 'value') else str(a.type)}）" for a in simulation.agents]
            lines.append("\n推演涉及实体列表：")
            lines.extend(agent_lines)

        lines.append("\n请基于以上初始信息，线性推演该事件在已推进的回合内的演化过程，并生成分析报告。")
        return "\n".join(lines)

    def _build_full_report(
        self,
        simulation: Simulation,
        agent_summaries: list[AgentSummary],
        overall_summary: str,
        conclusion: str,
    ) -> str:
        """组装 Markdown 完整基线报告"""
        lines = [
            f"# {simulation.name} 基线预测报告（纯 LLM 线性推演）",
            "",
            f"**推演回合**: {simulation.current_round} / {simulation.rounds}",
            f"**推演主线**: {simulation.config.main_line or '无'}",
            "",
            "> 说明：本报告基于初始事件信息，由单一 LLM 进行线性推演预测生成，未经过多 Agent 交互模拟。",
            "",
            "## 一、关键参与方分析",
            "",
        ]
        for s in agent_summaries:
            lines.append(f"### {s.agent_name}")
            lines.append(s.summary)
            lines.append("")

        lines.extend([
            "## 二、整体局势分析",
            "",
            overall_summary,
            "",
            "## 三、结论",
            "",
            conclusion,
            "",
        ])

        return "\n".join(lines)
