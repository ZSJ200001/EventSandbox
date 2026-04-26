import httpx
import os
import json
import time
from typing import Optional, Any
from pydantic import BaseModel
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """装饰器：失败时自动重试"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                        logger.warning(f"LLM调用失败，尝试重试 {attempt + 2}/{max_retries}: {e}")
            raise last_error
        return wrapper
    return decorator


class LLMConfig(BaseModel):
    api_base: str = "http://101.251.216.47/8411/v1"
    api_key: str = "sk-empty"
    default_model: str = "Qwen3-Coder-Next"
    timeout: float = 120.0
    max_tokens: int = 2048
    enable_few_shot: bool = True


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict
    finish_reason: str = ""


# ============== Few-Shot Examples ==============
FEW_SHOT_EXAMPLES = {
    "parse_entities": [
        {
            "input": "某大型互联网公司宣布裁员10%，引发员工不满和股价下跌",
            "output": {
                "entities": [
                    {"name": "某大型互联网公司", "type": "company", "description": "互联网行业巨头"},
                    {"name": "股东", "type": "individual", "description": "公司股东关注股价"},
                    {"name": "员工", "type": "individual", "description": "直接受影响群体"}
                ],
                "relationships": [
                    {"source": "员工", "target": "某大型互联网公司", "type": "demand", "strength": -0.3},
                    {"source": "股东", "target": "某大型互联网公司", "type": "influence", "strength": 0.2}
                ],
                "event_summary": "互联网公司宣布裁员导致股价下跌和员工不满"
            }
        },
        {
            "input": "华为发布新款MatePhone，苹果公司紧急召开会议讨论应对策略",
            "output": {
                "entities": [
                    {"name": "华为", "type": "company", "description": "中国领先的科技公司"},
                    {"name": "苹果公司", "type": "competitor", "description": "美国科技巨头，手机市场主要竞争者"},
                    {"name": "MatePhone", "type": "individual", "description": "华为新款手机产品"}
                ],
                "relationships": [
                    {"source": "华为", "target": "苹果公司", "type": "competitor", "strength": -0.6},
                    {"source": "苹果公司", "target": "华为", "type": "competitor", "strength": -0.6}
                ],
                "event_summary": "华为发布新品手机，苹果紧急讨论应对竞争策略"
            }
        }
    ],

    "decide_action": [
        {
            "input": {
                "agent": "XX奶茶",
                "type": "company",
                "personality": "进取、创新、关注市场份额",
                "goals": ["扩大市场份额", "提升品牌影响力", "增加利润"],
                "situation": "原材料成本上涨20%，竞品宣布降价5%，消费者开始关注价格",
                "available_actions": ["降价促销", "维持价格", "推出新品", "营销宣传", "优化供应链"]
            },
            "output": {
                "action": "推出新品",
                "reasoning": "面对成本压力和竞品降价，直接降价会压缩利润空间。推出新品可以重新定价，同时转移消费者对价格的注意力，符合品牌创新形象。",
                "expected_outcome": "通过新品发布吸引消费者关注，维持利润水平",
                "sentiment_change": 0.1,
                "target_agents": []
            }
        },
        {
            "input": {
                "agent": "小李",
                "type": "consumer",
                "personality": "理性、注重性价比",
                "goals": ["买到实惠产品", "维持生活品质"],
                "situation": "常喝的奶茶从15元涨到18元，同类品牌有更便宜的选择",
                "available_actions": ["继续购买", "换品牌", "减少购买频次", "投诉", "推荐替代品"]
            },
            "output": {
                "action": "换品牌",
                "reasoning": "价格上涨20%而品质没有提升，作为理性消费者会寻找替代品。竞品有更便宜的选择，换品牌是最合理的决定。",
                "expected_outcome": "找到性价比更高的替代产品",
                "sentiment_change": -0.1,
                "target_agents": ["XX奶茶"]
            }
        }
    ],

    "action_description": [
        {
            "input": {"agent": "监管部门", "action": "约谈企业负责人", "context": "某企业被投诉虚假宣传"},
            "output": "监管部门约谈某企业负责人，要求就虚假宣传问题进行说明，企业承诺整改。"
        },
        {
            "input": {"agent": "XX奶茶", "action": "推出新品", "context": "原材料成本上涨，竞品降价"},
            "output": "XX奶茶宣布推出全新系列饮品，采用升级配方，价格维持不变，以应对市场竞争。"
        }
    ]
}


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            config = LLMConfig()
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

    def _build_few_shot_messages(self, examples_key: str, user_prompt: str, system_prompt: str) -> list[LLMMessage]:
        """构建带 few-shot examples 的消息列表"""
        messages = [LLMMessage(role="system", content=system_prompt)]

        if self.config.enable_few_shot and examples_key in FEW_SHOT_EXAMPLES:
            examples = FEW_SHOT_EXAMPLES[examples_key]
            for ex in examples:
                messages.append(LLMMessage(role="user", content=str(ex["input"])))
                messages.append(LLMMessage(role="assistant", content=json.dumps(ex["output"], ensure_ascii=False)))

        messages.append(LLMMessage(role="user", content=user_prompt))
        return messages

    @retry_on_failure(max_retries=3, delay=1.0)
    def chat(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """发送聊天请求到 LLM API"""
        payload = {
            "model": model or self.config.default_model,
            "messages": [msg.model_dump() for msg in messages],
            "temperature": temperature,
        }

        actual_max_tokens = max_tokens or self.config.max_tokens
        payload["max_tokens"] = actual_max_tokens

        response = self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model or self.config.default_model),
            usage=data.get("usage", {}),
            finish_reason=data["choices"][0].get("finish_reason", ""),
        )

    def _parse_json_response(self, content: str, fallback: dict = None) -> dict:
        """解析 JSON 响应，支持多种格式"""
        fallback = fallback or {}

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 markdown 代码块
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取 {...} 格式
        brace_match = re.search(r'\{[\s\S]*\}', content)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法解析 JSON 响应，使用 fallback: {content[:200]}")
        return fallback

    # ============== Agent 个性生成 ==============
    def generate_agent_personality(
        self,
        agent_type: str,
        context: str,
        name: str,
        existing_agents: list[dict] = None
    ) -> dict:
        """为 Agent 生成个性和目标"""
        system_prompt = """你是一个多智能体仿真系统的人格生成专家。
根据智能体的类型和上下文，生成一个详细的人格画像，包括：
- personality: 3-5个形容词描述性格特征
- personality_traits: Big Five 各维度得分 (0.0-1.0)
  - openness: 开放性 (创造力、好奇心)
  - conscientiousness: 尽责性 (自律、责任心)
  - extraversion: 外向性 (社交能力)
  - agreeableness: 宜人性 (合作、信任)
  - neuroticism: 神经质 (情绪稳定性)
- goals: 2-4个核心目标
- beliefs: 关键信念列表
- description: 简短的角色描述
- strategy: 当前策略倾向 (aggressive/defensive/balanced/wait-and-see)

请以JSON格式返回。"""

        other_agents_info = ""
        if existing_agents:
            other_agents_info = "\n\n已知其他Agent:\n" + "\n".join([
                f"- {a.get('name', '未知')} ({a.get('type', 'unknown')})"
                for a in existing_agents[:5]
            ])

        user_prompt = f"""智能体类型: {agent_type}
角色名称: {name}
场景上下文: {context}
{other_agents_info}

生成一个符合该类型和上下文的人格画像。"""

        messages = self._build_few_shot_messages(
            "parse_entities",
            user_prompt,
            system_prompt
        )

        response = self.chat(messages, temperature=0.8, max_tokens=1024)

        base_result = self._parse_json_response(response.content, {
            "personality": "中立、谨慎",
            "personality_traits": {
                "openness": 0.5,
                "conscientiousness": 0.5,
                "extraversion": 0.5,
                "agreeableness": 0.5,
                "neuroticism": 0.5
            },
            "goals": ["生存", "发展"],
            "beliefs": [],
            "description": f"{name}是一个{agent_type}类型的角色",
            "strategy": "balanced"
        })

        # 确保 personality_traits 有所有必需字段
        default_traits = {
            "openness": 0.5, "conscientiousness": 0.5,
            "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5
        }
        if "personality_traits" in base_result:
            base_result["personality_traits"] = {**default_traits, **base_result["personality_traits"]}

        return base_result

    # ============== Action 决策 ==============
    def decide_action(
        self,
        agent_name: str,
        agent_type: str,
        agent_personality: str,
        agent_personality_traits: dict,
        agent_goals: list[str],
        current_situation: str,
        available_actions: list[str],
        knowledge_context: str = "",
        recent_history: str = "",
        relationships: list[dict] = None
    ) -> dict:
        """决定 Agent 应该采取的行动"""
        system_prompt = """你是一个多智能体仿真系统的决策引擎。
根据智能体的人格、目标、当前情况，决定应该采取什么行动。

决策原则：
1. 决策应该符合智能体的性格特征
2. 目标明确、逻辑连贯
3. 考虑与其他智能体的关系
4. 行动应产生可预见的结果

返回JSON格式：
{
    "action": "选择的行动（必须来自可用行动列表）",
    "reasoning": "决策理由（2-3句话）",
    "expected_outcome": "预期结果",
    "sentiment_change": -1.0 到 1.0（负面到正面）,
    "target_agents": ["目标智能体名称列表"],
    "action_intensity": 0.0 到 1.0（行动强度）,
    "risk_level": "low/medium/high"
}"""

        relationships_info = ""
        if relationships:
            relationships_info = "\n\n当前关系:\n" + "\n".join([
                f"- 与{r.get('target', '未知')}: {r.get('type', 'neutral')} (强度: {r.get('strength', 0)})"
                for r in relationships[:5]
            ])

        history_info = ""
        if recent_history:
            history_info = f"\n\n最近行动历史:\n{recent_history}"

        user_prompt = f"""智能体: {agent_name}
类型: {agent_type}
性格: {agent_personality}
性格特征: {agent_personality_traits}
目标: {', '.join(agent_goals)}
当前情况: {current_situation}
可用行动: {', '.join(available_actions)}
知识上下文: {knowledge_context}
{relationships_info}
{history_info}

做出决策。"""

        messages = self._build_few_shot_messages("decide_action", user_prompt, system_prompt)

        response = self.chat(messages, temperature=0.7, max_tokens=1024)

        return self._parse_json_response(response.content, {
            "action": available_actions[0] if available_actions else "观望",
            "reasoning": "默认决策",
            "expected_outcome": "维持现状",
            "sentiment_change": 0,
            "target_agents": [],
            "action_intensity": 0.5,
            "risk_level": "medium"
        })

    # ============== 实体解析 ==============
    def parse_event_entities(self, event_text: str) -> dict:
        """从文本中解析实体和关系"""
        system_prompt = """你是一个事件分析专家。
给定一个事件描述，识别其中包含的关键实体及其关系。

实体类型包括: company, competitor, consumer, supplier, government, regulator, organization, individual

关系类型包括: competitor(竞争), cooperative(合作), supply(供应), demand(需求), regulate(监管), influence(影响), neutral(中立)

返回JSON格式：
{
    "entities": [
        {"name": "实体名", "type": "类型", "description": "描述"}
    ],
    "relationships": [
        {"source": "实体1", "target": "实体2", "type": "关系类型", "strength": -1到1}
    ],
    "event_summary": "事件摘要"
}"""

        messages = self._build_few_shot_messages("parse_entities", f"事件: {event_text}", system_prompt)

        response = self.chat(messages, temperature=0.3, max_tokens=1024)

        return self._parse_json_response(response.content, {
            "entities": [],
            "relationships": [],
            "event_summary": event_text
        })

    # ============== 行动描述生成 ==============
    def generate_action_description(
        self,
        agent_name: str,
        action: str,
        context: str,
        target_agents: list[str] = None,
        action_intensity: float = 0.5
    ) -> str:
        """生成行动的自然语言描述"""
        system_prompt = """你是一个多智能体仿真的叙事生成器。
给定智能体名称、行动和上下文，生成简短而生动的描述（1-2句话）。
风格：像新闻报道一样客观陈述。"""

        target_info = ""
        if target_agents:
            target_info = f"\n影响目标: {', '.join(target_agents)}"

        intensity_desc = "采取行动" if action_intensity < 0.6 else "大力推进"

        user_prompt = f"""智能体: {agent_name}
行动: {action}
上下文: {context}
行动强度: {action_intensity}{target_info}

描述发生了什么。"""

        messages = self._build_few_shot_messages("action_description", user_prompt, system_prompt)

        response = self.chat(messages, temperature=0.7, max_tokens=256)
        return response.content.strip()

    # ============== 干预效果预测 ==============
    def predict_intervention_effect(
        self,
        intervention_type: str,
        intervention_value: str,
        target: str,
        current_situation: str,
        agents: list[dict]
    ) -> dict:
        """预测干预的效果"""
        system_prompt = """你是一个事件分析专家。
给定一个干预措施，预测其对仿真可能产生的影响。

返回JSON格式：
{
    "predicted_effects": {
        "affected_metrics": {"metric_name": 预期变化值},
        "affected_agents": ["agent1", "agent2"],
        "sentiment_changes": {"agent_name": 变化值}
    },
    "cascade_probability": 0.0到1.0（连锁反应概率）,
    "severity": 0.0到1.0（影响严重程度）,
    "duration": "即时/短期/中期/长期",
    "reversibility": true或false
}"""

        agents_info = "\n".join([
            f"- {a.get('name', '未知')} ({a.get('type', 'unknown')})"
            for a in agents[:5]
        ])

        user_prompt = f"""干预类型: {intervention_type}
干预内容: {intervention_value}
目标: {target if target else '全局'}
当前情况: {current_situation}

相关智能体:
{agents_info}

预测干预效果。"""

        messages = [LLMMessage(role="system", content=system_prompt)]
        messages.append(LLMMessage(role="user", content=user_prompt))

        response = self.chat(messages, temperature=0.5, max_tokens=512)

        return self._parse_json_response(response.content, {
            "predicted_effects": {
                "affected_metrics": {},
                "affected_agents": [],
                "sentiment_changes": {}
            },
            "cascade_probability": 0.3,
            "severity": 0.5,
            "duration": "短期",
            "reversibility": True
        })

    # ============== 场景分析 ==============
    def analyze_scenario_trend(
        self,
        simulation_state: dict,
        metrics_history: list[dict]
    ) -> dict:
        """分析场景趋势"""
        system_prompt = """你是一个数据分析专家。
分析给定仿真场景的历史数据和当前状态，判断发展趋势。

返回JSON格式：
{
    "trend": "上升/下降/稳定/波动",
    "confidence": 0.0到1.0,
    "key_changes": ["主要变化点1", "主要变化点2"],
    "predictions": ["预测1", "预测2"],
    "warnings": ["预警1"],
    "opportunities": ["机会1"]
}"""

        user_prompt = f"""当前状态: {json.dumps(simulation_state, ensure_ascii=False, indent=2)}

指标历史: {json.dumps(metrics_history, ensure_ascii=False)}

分析趋势。"""

        messages = [LLMMessage(role="system", content=system_prompt)]
        messages.append(LLMMessage(role="user", content=user_prompt))

        response = self.chat(messages, temperature=0.5, max_tokens=512)

        return self._parse_json_response(response.content, {
            "trend": "稳定",
            "confidence": 0.5,
            "key_changes": [],
            "predictions": [],
            "warnings": [],
            "opportunities": []
        })

    # ============== 健康检查 ==============
    def is_healthy(self) -> bool:
        """检查 LLM API 是否可达"""
        try:
            self.client.get("/models", timeout=5)
            return True
        except Exception:
            return False

    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
        return self.config.default_model

    def close(self):
        """关闭客户端"""
        self.client.close()


# ============== 全局客户端实例 ==============
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def reset_llm_client():
    """重置全局 LLM 客户端（用于配置更改后）"""
    global _llm_client
    if _llm_client:
        _llm_client.close()
    _llm_client = None
