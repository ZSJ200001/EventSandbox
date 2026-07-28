"""异步 LLM 客户端。

核心改进：
- 使用 httpx.AsyncClient 替代同步 Client，支持并发请求
- 自动重试 + 指数退避
- 多层 JSON 解析容错
- 所有方法返回结构化 Pydantic 模型
"""

import asyncio
import json
import logging
import re
from typing import Any, Optional

import httpx
from json_repair import repair_json
from pydantic import ValidationError

from core.config import get_settings
from core.exceptions import LLMError
from .schemas import (
    LLMConfig,
    LLMMessage,
    LLMResponse,
    AgentDecisionOutput,
    EntityExtractionOutput,
    EntityAttributesOutput,
    RelationshipExtractionOutput,
    ScenarioWorldModelOutput,
    ExternalImpactOutput,
    WorldStateUpdateOutput,
    MainLinePressureOutput,
    InterventionOptionsOutput,
)
from . import prompts

logger = logging.getLogger(__name__)


class AsyncLLMClient:
    """异步 LLM 客户端"""

    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            settings = get_settings()
            config = LLMConfig(
                api_base=settings.llm_api_base,
                api_key=settings.llm_api_key,
                default_model=settings.default_model,
                timeout=settings.llm_timeout,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                enable_few_shot=settings.llm_enable_few_shot,
                max_retries=settings.llm_max_retries,
                retry_delay=settings.llm_retry_delay,
            )

        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.api_base,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout,
        )
        logger.info(
            "[AsyncLLMClient] 初始化完成, api_base=%s, model=%s",
            config.api_base,
            config.default_model,
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        method: str = "chat",
    ) -> LLMResponse:
        """发送聊天请求，带自动重试"""
        payload = {
            "model": model or self.config.default_model,
            "messages": [msg.model_dump() for msg in messages],
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "chat_template_kwargs": {
                "enable_thinking": False
            },
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.debug("[LLM] %s 请求 attempt=%d/%d", method, attempt, self.config.max_retries)
                response = await self.client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()

                result = LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data.get("model", model or self.config.default_model),
                    usage=data.get("usage", {}),
                    finish_reason=data["choices"][0].get("finish_reason", ""),
                )
                logger.debug("[LLM] %s 成功, tokens=%s", method, result.usage)
                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "[LLM] %s 失败 attempt=%d/%d, error=%s",
                    method,
                    attempt,
                    self.config.max_retries,
                    e,
                )
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * attempt
                    logger.info("[LLM] %s 等待 %.1fs 后重试...", method, delay)
                    await asyncio.sleep(delay)

        logger.error("[LLM] %s 重试耗尽, error=%s", method, last_error)
        raise LLMError(f"{method} 调用失败（已重试{self.config.max_retries}次）: {last_error}")

    def _build_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        few_shot_key: Optional[str] = None,
    ) -> list[LLMMessage]:
        """构建消息列表，支持 few-shot"""
        messages = [LLMMessage(role="system", content=system_prompt)]

        if self.config.enable_few_shot and few_shot_key:
            examples = prompts.FEW_SHOT_EXAMPLES.get(few_shot_key, [])
            for ex in examples:
                messages.append(LLMMessage(role="user", content=str(ex["input"])))
                messages.append(
                    LLMMessage(role="assistant", content=json.dumps(ex["output"], ensure_ascii=False))
                )

        messages.append(LLMMessage(role="user", content=user_prompt))
        return messages

    @staticmethod
    def _parse_json(content: str, fallback: dict, method: str = "") -> dict:
        """JSON 解析容错（优先使用 json_repair 修复）"""
        last_error: Optional[Exception] = None

        # 使用 json_repair 修复并解析
        try:
            repaired = repair_json(content)
            result = json.loads(repaired)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, Exception) as e:
            last_error = e
            logger.debug("[LLM] json_repair 修复失败: %s, 尝试 fallback 解析...", e)

        # markdown 代码块提取
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if match:
            try:
                repaired = repair_json(match.group(1))
                result = json.loads(repaired)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, Exception) as e:
                last_error = e

        # 花括号提取
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                repaired = repair_json(match.group())
                result = json.loads(repaired)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, Exception) as e:
                last_error = e

        logger.warning(
            "[LLM] JSON 解析失败 [%s], 原始输出前200字符: %s, 原因: %s",
            method or "unknown",
            content[:200],
            last_error,
        )
        return fallback

    # ============== 业务方法 ==============

    async def generate_agent_personality(
        self, agent_type: str, context: str, name: str, existing_agents: Optional[list[dict]] = None
    ) -> dict:
        """生成 Agent 人格画像"""
        logger.info("[LLM] generate_agent_personality 开始, name=%s, type=%s", name, agent_type)
        other_info = ""
        if existing_agents:
            other_info = "\n\n已知其他Agent:\n" + "\n".join(
                [f"- {a.get('name', '未知')} ({a.get('type', 'unknown')})" for a in existing_agents[:5]]
            )

        user_prompt = f"""智能体类型: {agent_type}
角色名称: {name}
场景上下文: {context}
{other_info}

生成一个符合该类型和上下文的人格画像。"""

        messages = self._build_messages(
            prompts.SYS_GENERATE_PERSONALITY, user_prompt
        )
        response = await self.chat(messages, temperature=0.8, max_tokens=1024, method="generate_agent_personality")
        data = self._parse_json(
            response.content,
            {
                "personality": "中立、谨慎",
                "goals": ["生存", "发展"],
            },
            method=__name__,
        )
        logger.info("[LLM] generate_agent_personality 完成, name=%s", name)
        return data

    async def decide_action(
        self,
        agent_name: str,
        agent_type: str,
        agent_personality: str,
        agent_description: str,
        agent_goals: list[str],
        current_situation: str,
        visible_actions: list[dict],
        environment_state: dict,
        knowledge_context: str = "",
        recent_history: str = "",
        relationships: Optional[list[dict]] = None,
        is_forced_response: bool = False,
        all_agents: Optional[list[dict]] = None,
        time_context: Optional[dict] = None,
        event_types: Optional[list[str]] = None,
    ) -> AgentDecisionOutput:
        """Agent 决策（精简版：去掉五维人格分数，用 description 替代 deep_profile）"""
        logger.info("[LLM] decide_action 开始, agent=%s", agent_name)

        relationships_info = ""
        if relationships:
            relationships_info = "\n\n【你当前主动建立的关系】\n" + "\n".join(
                [
                    f"- 关系ID: {r.get('relation_id', '未知')} | 原实体: {r.get('source_name', '未知')}({r.get('source_id', '')}) | "
                    f"目标实体: {r.get('target_name', '未知')}({r.get('target_id', '')}) | 关系: {r.get('relation', 'neutral')} | "
                    f"描述: {r.get('description', '')}"
                    for r in relationships[:8]
                ]
            )

        history_info = f"\n\n【最近行动历史】\n{recent_history}" if recent_history else ""

        visible_info = ""
        if visible_actions:
            visible_info = "\n\n【本轮你收到的信息】\n" + "\n".join(
                [
                    f"- {a.get('agent_name', '未知')} ({a.get('visibility', '公开')}): {a.get('description', '')}"
                    for a in visible_actions[-10:]
                ]
            )

        env_info = ""
        if environment_state:
            env_info = "\n\n【当前环境状态】\n" + "\n".join([f"- {k}: {v}" for k, v in environment_state.items()])

        forced_hint = ""
        if is_forced_response:
            forced_hint = "\n\n【注意】你本轮受到了针对你的行动，必须做出回应，不能选择观望。"

        agents_info = ""
        if all_agents:
            agents_info = "\n\n【所有实体】\n" + "\n".join(
                [f"- ID: {a.get('id', '未知')} | 名称: {a.get('name', '未知')} | 类型: {a.get('type', 'unknown')}" for a in all_agents]
            )

        time_info = ""
        if time_context and time_context.get("has_time_semantics"):
            time_info = f"""\n\n【时间上下文】
- 推演开始时间：{time_context.get('start_datetime', '未知')}
- 当前模拟时间：{time_context.get('current_simulated_time', '未知')}
- 当前是第 {time_context.get('current_round', '?')} / {time_context.get('total_rounds', '?')} 回合
- 每回合代表：{time_context.get('round_duration', '未知')}
- 距离推演结束还有 {time_context.get('remaining_rounds', '?')} 个决策窗口

请注意：你的行动应符合当前模拟时间尺度。"""

        event_types_info = ""
        if event_types:
            event_types_info = "\n\n【本场景事件类型】\n" + ", ".join(event_types)

        user_prompt = f"""【角色】{agent_name}（{agent_type}）
【性格标签】{agent_personality}
【角色描述】{agent_description}
【核心目标】{', '.join(agent_goals)}

{agents_info}

【当前局势】
{current_situation}
{visible_info}
{env_info}
{event_types_info}
{relationships_info}
{history_info}
{time_info}
{forced_hint}

请做出决策。"""

        messages = self._build_messages(
            prompts.SYS_DECIDE_ACTION,
            user_prompt,
            few_shot_key="decide_action",
        )
        response = await self.chat(messages, temperature=0.7, max_tokens=2048, method="decide_action")

        fallback = {
            "action": "观望/不行动",
            "reasoning": "默认决策",
            "expected_outcome": "维持现状",
            "sentiment_change": 0,
            "target_agents": [],
            "action_description": "",
            "relation_changes": [],
        }
        data = self._parse_json(response.content, fallback, method=__name__)
        logger.info("[LLM] decide_action 完成, agent=%s, action=%s", agent_name, data.get("action"))
        return AgentDecisionOutput.model_validate(data)

    async def generate_action_description(
        self,
        agent_name: str,
        action: str,
        context: str,
        target_agents: Optional[list[str]] = None,
    ) -> str:
        """生成行动自然语言描述"""
        target_info = f"\n影响目标: {', '.join(target_agents)}" if target_agents else ""
        user_prompt = f"""智能体: {agent_name}
行动: {action}
上下文: {context}{target_info}

描述发生了什么。"""

        messages = self._build_messages(
            prompts.SYS_GENERATE_ACTION_DESCRIPTION,
            user_prompt,
            few_shot_key="action_description",
        )
        response = await self.chat(messages, temperature=0.7, max_tokens=256, method="generate_action_description")
        return response.content.strip()

    async def aggregate_world_state_updates(
        self,
        current_world_state: dict[str, Any],
        world_state_schema: dict[str, str],
        round_actions: list[dict],
        relation_changes: list[dict],
        current_round: int,
        time_context: Optional[dict] = None,
    ) -> WorldStateUpdateOutput:
        """汇总本回合所有 Agent 行动，推导世界状态变化"""
        logger.info("[LLM] aggregate_world_state_updates 开始, round=%d, actions=%d", current_round, len(round_actions))

        schema_info = "\n".join([f"- {k} ({v})" for k, v in world_state_schema.items()]) or "暂无 schema"
        state_info = "\n".join([f"- {k}: {v}" for k, v in current_world_state.items()]) or "暂无"
        actions_info = "\n".join(
            [f"- {a.get('agent_name', '未知')}: {a.get('action', '')} | {a.get('action_description', '')}" for a in round_actions]
        )
        relations_info = "\n".join(
            [f"- {c.get('source_name', '')} -> {c.get('target_name', '')}: {c.get('before_relation', '')} -> {c.get('after_relation', '')}"
             for c in relation_changes[:20]]
        ) or "本回合无直接关系变化"

        time_info = ""
        if time_context and time_context.get("has_time_semantics"):
            time_info = f"""
【时间上下文】
- 推演开始时间：{time_context.get('start_datetime', '未知')}
- 当前模拟时间：{time_context.get('current_simulated_time', '未知')}
- 每回合代表：{time_context.get('round_duration', '未知')}
- 当前是第 {time_context.get('current_round', '?')} / {time_context.get('total_rounds', '?')} 回合

请注意：推导世界状态时应以当前模拟时间为时间基准。"""

        user_prompt = f"""当前回合: {current_round}{time_info}

【需要跟踪的世界状态字段】
{schema_info}

【当前世界状态】
{state_info}

【本回合 Agent 行动】
{actions_info}

【本回合关系变化】
{relations_info}"""

        fallback = {
            "world_state_updates": {},
            "reasoning": "默认无变化",
        }
        messages = self._build_messages(
            prompts.SYS_AGGREGATE_WORLD_STATE,
            user_prompt,
            few_shot_key=None,
        )
        response = await self.chat(messages, temperature=0.5, max_tokens=512, method="aggregate_world_state_updates")
        data = self._parse_json(response.content, fallback, method=__name__)
        logger.info("[LLM] aggregate_world_state_updates 完成, updates=%s", data.get("world_state_updates", {}))
        return WorldStateUpdateOutput.model_validate(data)

    async def analyze_external_impact(
        self,
        simulation_name: str,
        simulation_description: str,
        agents: list[dict],
        current_relations: list[dict],
        external_events: list[dict],
        current_round: int,
    ) -> ExternalImpactOutput:
        """分析外部事件对关系的影响"""
        logger.info("[LLM] analyze_external_impact 开始, round=%d, events=%d", current_round, len(external_events))
        agents_info = "\n".join(
            [f"- {a.get('name', '未知')} (ID: {a.get('id', '')}, 类型: {a.get('type', '未知')})" for a in agents[:10]]
        )
        relations_info = (
            "\n".join(
                [
                    f"- 关系ID: {r.get('relation_id', '')} | {r.get('source_name', '')}({r.get('source_id', '')}) -> "
                    f"{r.get('target_name', '')}({r.get('target_id', '')}): {r.get('relation', '')}"
                    for r in current_relations[:15]
                ]
            )
            if current_relations
            else "暂无明确关系"
        )
        events_info = "\n".join(
            [f"- 第{e.get('round', '?')}回合 [{e.get('type', '')}]: {e.get('description', '')}" for e in external_events]
        )

        user_prompt = f"""推演: {simulation_name}
描述: {simulation_description}
当前回合: {current_round}

参与Agent:
{agents_info}

当前关系网络:
{relations_info}

本回合外部事件:
{events_info}

请分析这些外部事件对各Agent关系的影响。"""

        messages = [
            LLMMessage(role="system", content=prompts.SYS_ANALYZE_EXTERNAL_IMPACT),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await self.chat(messages, temperature=0.7, max_tokens=1024, method="analyze_external_impact")
        data = self._parse_json(response.content, {"relation_updates": [], "agent_logs": {}}, method=__name__)
        logger.info("[LLM] analyze_external_impact 完成, updates=%d", len(data.get("relation_updates", [])))
        return ExternalImpactOutput.model_validate(data)

    async def generate_intervention_options(
        self,
        simulation_name: str,
        simulation_description: str,
        agents: list[dict],
        recent_events: list[dict],
        current_round: int,
    ) -> InterventionOptionsOutput:
        """生成全局干预选项"""
        logger.info("[LLM] generate_intervention_options 开始, round=%d", current_round)
        agents_info = "\n".join(
            [f"- {a.get('name', '未知')} ({a.get('type', '未知')}): {a.get('description', '')}" for a in agents[:8]]
        )
        events_info = (
            "\n".join([f"- 第{e.get('round', '?')}回合: {e.get('description', '')[:60]}" for e in recent_events[-5:]])
            if recent_events
            else "暂无近期事件"
        )

        user_prompt = f"""推演名称: {simulation_name}
推演描述: {simulation_description}
当前回合: {current_round}

参与Agent:
{agents_info}

近期事件:
{events_info}

请生成贴合当前场景的干预选项。"""

        messages = self._build_messages(
            prompts.SYS_GENERATE_INTERVENTION_OPTIONS,
            user_prompt,
            few_shot_key="generate_intervention_options",
        )
        response = await self.chat(messages, temperature=0.8, max_tokens=1024, method="generate_intervention_options")
        data = self._parse_json(
            response.content,
            {
                "event_options": [],
                "agent_options": [],
                "env_options": [],
            },
            method=__name__,
        )
        logger.info("[LLM] generate_intervention_options 完成")
        return InterventionOptionsOutput.model_validate(data)

    async def generate_main_line_pressure(
        self,
        main_line: str,
        agents: list[dict],
        recent_events: list[dict],
        current_round: int,
    ) -> MainLinePressureOutput:
        """根据主线为关键 Agent 生成压力提示"""
        if not main_line:
            return MainLinePressureOutput()

        logger.info("[LLM] generate_main_line_pressure 开始, round=%d, agents=%d", current_round, len(agents))
        agents_info = "\n".join(
            [f"- {a.get('name', '未知')} ({a.get('type', '未知')}): {a.get('description', '')}" for a in agents[:10]]
        )
        events_info = (
            "\n".join([f"- 第{e.get('round', '?')}回合: {e.get('description', '')[:80]}" for e in recent_events[-5:]])
            if recent_events
            else "暂无近期事件"
        )

        user_prompt = f"""推演主线: {main_line}
当前回合: {current_round}

参与Agent:
{agents_info}

近期事件:
{events_info}

请为关键 Agent 生成主线压力提示。"""

        messages = [
            LLMMessage(role="system", content=prompts.SYS_GENERATE_MAIN_LINE_PRESSURE),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await self.chat(messages, temperature=0.7, max_tokens=1024, method="generate_main_line_pressure")
        data = self._parse_json(
            response.content,
            {"pressures": {}},
            method=__name__,
        )
        logger.info(
            "[LLM] generate_main_line_pressure 完成, pressures=%d",
            len(data.get("pressures", {})),
        )
        return MainLinePressureOutput.model_validate(data)

    # ============== 分步实体提取 =============="}

    async def extract_entities(self, event_text: str) -> EntityExtractionOutput:
        """第一步：从文本中提取实体"""
        logger.info("[LLM] extract_entities 开始, text=%s...", event_text[:50])
        messages = [
            LLMMessage(role="system", content=prompts.SYS_EXTRACT_ENTITIES),
            LLMMessage(role="user", content=f"事件描述：\n{event_text}"),
        ]
        response = await self.chat(messages, temperature=0.3, max_tokens=1024, method="extract_entities")
        data = self._parse_json(
            response.content,
            {"entities": [], "is_complete": True, "reasoning": ""},
            method=__name__,
        )
        logger.info("[LLM] extract_entities 完成, entities=%d", len(data.get("entities", [])))
        return EntityExtractionOutput.model_validate(data)

    async def check_missing_entities(
        self, event_text: str, existing_entities: list[dict]
    ) -> EntityExtractionOutput:
        """检查是否有遗漏实体"""
        logger.info("[LLM] check_missing_entities 开始, existing=%d", len(existing_entities))
        existing_info = "\n".join(
            [f"- {e.get('name', '未知')} ({e.get('type', 'unknown')})" for e in existing_entities]
        )
        user_prompt = f"""原始事件描述：
{event_text}

已提取的实体列表：
{existing_info}

请检查是否有遗漏的重要实体。"""
        messages = [
            LLMMessage(role="system", content=prompts.SYS_CHECK_MISSING_ENTITIES),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await self.chat(messages, temperature=0.3, max_tokens=1024, method="check_missing_entities")
        data = self._parse_json(
            response.content,
            {"additional_entities": [], "is_complete": True, "reasoning": ""},
            method=__name__,
        )
        # 合并为统一格式
        result = EntityExtractionOutput(
            entities=data.get("additional_entities", []),
            is_complete=data.get("is_complete", True),
            reasoning=data.get("reasoning", ""),
        )
        logger.info(
            "[LLM] check_missing_entities 完成, additional=%d, is_complete=%s",
            len(result.entities),
            result.is_complete,
        )
        return result

    async def build_entity_attributes(
        self, entity_name: str, entity_type: str, context: str
    ) -> EntityAttributesOutput:
        """第二步：为单个实体构建属性"""
        logger.info("[LLM] build_entity_attributes 开始, name=%s, type=%s", entity_name, entity_type)
        user_prompt = f"""实体名称: {entity_name}
实体类型: {entity_type}
事件上下文: {context}

请为该实体生成核心属性和描述。"""
        messages = [
            LLMMessage(role="system", content=prompts.SYS_BUILD_ENTITY_ATTRIBUTES),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await self.chat(messages, temperature=0.5, max_tokens=768, method="build_entity_attributes")
        data = self._parse_json(
            response.content,
            {
                "description": f"{entity_name}是{entity_type}类型的实体",
                "attributes": {},
                "keywords": [],
                "is_actionable": True,
                "controller": "",
            },
            method=__name__,
        )
        logger.info("[LLM] build_entity_attributes 完成, name=%s", entity_name)
        return EntityAttributesOutput.model_validate(data)

    async def extract_relationships(
        self, event_text: str, entities_info: list[dict]
    ) -> RelationshipExtractionOutput:
        """第三步：提取实体间关系"""
        logger.info("[LLM] extract_relationships 开始, entities=%d", len(entities_info))
        entities_str = "\n".join(
            [
                f"- {e.get('name', '未知')} (类型: {e.get('type', 'unknown')}, 描述: {e.get('description', '')[:60]})"
                for e in entities_info
            ]
        )
        user_prompt = f"""原始事件描述：
{event_text}

已提取的实体：
{entities_str}

请提取这些实体之间的关系。"""
        messages = [
            LLMMessage(role="system", content=prompts.SYS_EXTRACT_RELATIONSHIPS),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await self.chat(messages, temperature=0.3, max_tokens=1536, method="extract_relationships")
        data = self._parse_json(
            response.content,
            {"relationships": [], "event_summary": event_text, "scene_ontology": ""},
            method=__name__,
        )
        logger.info(
            "[LLM] extract_relationships 完成, relationships=%d",
            len(data.get("relationships", [])),
        )
        return RelationshipExtractionOutput.model_validate(data)

    async def extract_world_model(
        self,
        event_text: str,
        entities_info: Optional[list[dict]] = None,
        main_line: str = "",
        time_context: Optional[dict] = None,
    ) -> ScenarioWorldModelOutput:
        """提取场景世界模型说明（方案 C）"""
        logger.info("[LLM] extract_world_model 开始, text=%s...", event_text[:50])
        entities_str = ""
        if entities_info:
            entities_str = "\n".join(
                [
                    f"- {e.get('name', '未知')} (类型: {e.get('type', 'unknown')}, 描述: {e.get('description', '')[:60]})"
                    for e in entities_info
                ]
            )

        main_line_info = f"\n推演主线（核心问题）: {main_line}" if main_line else ""

        time_info = ""
        if time_context and time_context.get("has_time_semantics"):
            time_info = f"""
【时间上下文】
- 推演开始时间：{time_context.get('start_datetime', '未知')}
- 当前模拟时间：{time_context.get('current_simulated_time', '未知')}
- 每回合代表：{time_context.get('round_duration', '未知')}
- 推演总回合数：{time_context.get('total_rounds', '?')}

请注意：initial_world_state 中的时间相关字段应与上述推演开始时间/当前模拟时间保持一致。事件描述中提到的具体日期属于模拟时间线，不要混用真实历史年份。"""

        user_prompt = f"""初始事件描述：
{event_text}
{main_line_info}
{time_info}

已提取的实体：
{entities_str or '暂无'}

请根据以上信息输出场景世界模型说明。"""

        messages = [
            LLMMessage(role="system", content=prompts.SYS_EXTRACT_WORLD_MODEL),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await self.chat(messages, temperature=0.3, max_tokens=1536, method="extract_world_model")
        data = self._parse_json(
            response.content,
            {
                "scenario_type": "generic",
                "world_state_schema": {},
                "event_types": [],
                "terminal_condition": "",
                "action_grammar": "",
                "initial_world_state": {},
                "outcome_evaluation": "",
            },
            method=__name__,
        )
        logger.info("[LLM] extract_world_model 完成, type=%s", data.get("scenario_type"))
        return ScenarioWorldModelOutput.model_validate(data)

    async def is_healthy(self) -> bool:
        """检查 LLM API 是否可达"""
        try:
            await self.client.get("/models", timeout=5)
            return True
        except Exception as e:
            logger.warning("[LLM] 健康检查失败: %s", e)
            return False

    def get_model_name(self) -> str:
        return self.config.default_model

    async def close(self) -> None:
        await self.client.aclose()
        logger.info("[AsyncLLMClient] 连接已关闭")
