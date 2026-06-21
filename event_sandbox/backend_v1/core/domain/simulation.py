"""推演领域模型"""

import ast
import operator
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from .common import SimulationStatus
from .agent import Agent
from .event import Event
from .relation import RelationEdge
from .world_model import ScenarioWorldModel, WorldEvent


# 时间单位到 timedelta 的映射（month/year 用近似值）
TIME_UNIT_DAYS = {
    "minute": 1 / 1440,
    "hour": 1 / 24,
    "day": 1,
    "week": 7,
    "month": 30,
    "quarter": 90,
    "year": 365,
}


def _generate_short_id() -> str:
    """生成8位十六进制短ID"""
    return secrets.token_hex(4)


def add_simulated_duration(base: datetime, value: float, unit: str) -> datetime:
    """根据时间单位增加模拟时长"""
    if unit == "round" or unit not in TIME_UNIT_DAYS:
        return base
    days = TIME_UNIT_DAYS[unit] * value
    return base + timedelta(days=days)


def format_simulated_time(dt: datetime) -> str:
    """格式化模拟时间"""
    return dt.strftime("%Y-%m-%d %H:%M")


def duration_label(value: float, unit: str) -> str:
    """生成可读的时间单位描述"""
    unit_labels = {
        "minute": "分钟",
        "hour": "小时",
        "day": "天",
        "week": "周",
        "month": "月",
        "quarter": "季度",
        "year": "年",
        "round": "回合",
    }
    return f"{value}{unit_labels.get(unit, unit)}"


class TimelineEntry(BaseModel):
    """推演时间轴条目"""

    round: int
    type: str = "agent_action"          # agent_action | external_event | agent_added
    actor: str = ""                     # Agent 名称或 "系统"
    action: str = ""                    # 动作标签
    description: str = ""               # 自然语言描述
    before: Optional[dict] = None       # 变化前状态 {"relation": "...", "polarity": "..."}
    after: Optional[dict] = None        # 变化后状态
    details: dict = Field(default_factory=dict)  # 扩展字段：reasoning, sentiment_change, target_agents, relation_updates 等


class RoundSummary(BaseModel):
    """回合摘要"""

    round: int
    summary: str = ""
    key_events: list[str] = Field(default_factory=list)
    significance: str = "normal"        # normal | important | critical


class SimulationConfig(BaseModel):
    """推演配置"""

    max_rounds: int = 10
    llm_model: str = "Qwen3-Coder-Next"
    temperature: float = 0.7
    knowledge_enabled: bool = True
    visualization_interval: int = 1

    enable_memory: bool = True
    enable_cascade: bool = True
    cascade_probability: float = 0.3
    enable_random_events: bool = True
    random_event_probability: float = 0.1

    decision_iterations: int = 1
    use_few_shot: bool = True

    main_line: str = ""  # 推演主线，用于引导 Agent 决策方向

    # 时间切片配置
    start_datetime: datetime = Field(default_factory=datetime.now)  # 推演起始时间
    round_duration_value: float = 1.0                               # 每回合时长数值
    round_duration_unit: str = "round"                              # 时间单位：minute/hour/day/week/month/quarter/year/round

    def get_current_simulated_time(self, current_round: int) -> datetime:
        """根据当前回合计算模拟时间"""
        return add_simulated_duration(self.start_datetime, self.round_duration_value * current_round, self.round_duration_unit)

    @property
    def has_time_semantics(self) -> bool:
        """是否启用了时间语义"""
        return self.round_duration_unit != "round"

    @property
    def duration_label(self) -> str:
        """生成可读的时间单位描述"""
        return duration_label(self.round_duration_value, self.round_duration_unit)


class SimulationMetrics(BaseModel):
    """推演指标"""

    cooperation_level: float = 0.0
    conflict_level: float = 0.0
    action_diversity: float = 0.0
    information_entropy: float = 0.0
    initiative_index: float = 0.0
    network_turbulence: float = 0.0
    custom_metrics: dict[str, float] = Field(default_factory=dict)

    def to_display_dict(self) -> dict:
        return {
            "cooperation_level": self.cooperation_level,
            "conflict_level": self.conflict_level,
            "action_diversity": self.action_diversity,
            "information_entropy": self.information_entropy,
            "initiative_index": self.initiative_index,
            "network_turbulence": self.network_turbulence,
        }


class TopologyNode(BaseModel):
    """拓扑节点"""

    id: str
    label: str
    node_type: str = "agent"
    agent_id: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    metadata: dict = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    """拓扑边"""

    source: str
    target: str
    relation: str = ""
    edge_type: str = "agent_relation"
    weight: float = 0.5
    label: str = ""
    description: str = ""
    round: int = 0
    is_active: bool = True
    expires_at_round: Optional[int] = None
    interaction_count: int = 0
    last_interaction_round: int = 0


class Topology(BaseModel):
    """拓扑结构"""

    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)

    def find_node(self, node_id: str, node_type: Optional[str] = None) -> Optional[TopologyNode]:
        for n in self.nodes:
            if n.id == node_id:
                if node_type is None or n.node_type == node_type:
                    return n
        return None

    def find_edge(
        self, source: str, target: str, edge_type: Optional[str] = None, directed: bool = False
    ) -> Optional[TopologyEdge]:
        for e in self.edges:
            if directed:
                match = e.source == source and e.target == target
            else:
                match = (e.source == source and e.target == target) or \
                        (e.source == target and e.target == source)
            if match:
                if edge_type is None or e.edge_type == edge_type:
                    return e
        return None

    def remove_agent_nodes(self, agent_id: str) -> dict:
        before_nodes = len(self.nodes)
        before_edges = len(self.edges)
        self.nodes = [n for n in self.nodes if n.agent_id != agent_id]
        keep_ids = {n.id for n in self.nodes}
        self.edges = [e for e in self.edges if e.source in keep_ids and e.target in keep_ids]
        return {
            "nodes_removed": before_nodes - len(self.nodes),
            "edges_removed": before_edges - len(self.edges),
        }


class Simulation(BaseModel):
    """推演实体"""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_generate_short_id)
    name: str
    description: str = ""

    agents: list[Agent] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    relations: list[RelationEdge] = Field(default_factory=list)
    topology: Topology = Field(default_factory=Topology)

    rounds: int = 10
    current_round: int = 0
    status: SimulationStatus = SimulationStatus.PENDING
    metrics: SimulationMetrics = Field(default_factory=SimulationMetrics)

    # 当前模拟时间（由 config 计算得出，创建和推进时自动同步）
    current_simulated_time: datetime = Field(default_factory=datetime.now)

    ontology_summary: str = ""
    environment_state: dict = Field(default_factory=dict)

    # 场景感知世界模型（方案 C）
    world_model: Optional[ScenarioWorldModel] = None
    world_state: dict[str, Any] = Field(default_factory=dict)
    world_state_history: list[dict[str, Any]] = Field(default_factory=list)
    world_events_history: list[WorldEvent] = Field(default_factory=list)

    # 统一推演日志（替代旧的 round_actions）
    timeline: list[TimelineEntry] = Field(default_factory=list)
    round_summaries: list[RoundSummary] = Field(default_factory=list)
    metrics_history: list[dict] = Field(default_factory=list)

    start_time: Optional[int] = None
    end_time: Optional[int] = None
    interventions: list[dict] = Field(default_factory=list)
    config: SimulationConfig = Field(default_factory=SimulationConfig)
    critical_nodes: list[int] = Field(default_factory=list)

    # 报告（持久化存储）
    report: dict = Field(default_factory=dict)
    baseline_report: dict = Field(default_factory=dict)

    # 列表查询用的计数字段（避免加载完整 agents/events）
    agent_count: int = 0
    event_count: int = 0

    def model_post_init(self, __context) -> None:
        """创建后自动同步当前模拟时间"""
        self.current_simulated_time = self.config.get_current_simulated_time(self.current_round)

    def update_simulated_time(self) -> None:
        """回合推进后更新模拟时间"""
        self.current_simulated_time = self.config.get_current_simulated_time(self.current_round)

    def get_time_context(self) -> dict:
        """获取时间上下文供 LLM 使用"""
        return {
            "current_round": self.current_round,
            "total_rounds": self.rounds,
            "current_simulated_time": format_simulated_time(self.current_simulated_time),
            "start_datetime": format_simulated_time(self.config.start_datetime),
            "round_duration": self.config.duration_label,
            "has_time_semantics": self.config.has_time_semantics,
        }

    # ============== 场景感知世界模型方法（方案 C）==============

    def update_world_state(self, updates: dict[str, Any]) -> dict[str, Any]:
        """应用世界状态更新，返回变更前状态"""
        before = dict(self.world_state)
        for key, value in updates.items():
            if value is None:
                continue
            # 若 schema 中声明为数字类型，尝试转换
            schema_type = (self.world_model.world_state_schema.get(key) if self.world_model else "")
            if schema_type in ("number", "int", "float"):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    pass
            self.world_state[key] = value
        return before

    def snapshot_world_state(self, round_num: int) -> None:
        """记录当前世界状态快照"""
        self.world_state_history.append({
            "round": round_num,
            "state": dict(self.world_state),
        })

    def add_world_event(self, event: WorldEvent) -> None:
        """追加离散世界事件"""
        self.world_events_history.append(event)

    def get_world_state_context(self) -> str:
        """生成给 LLM 的世界状态描述文本"""
        if not self.world_state:
            return "暂无特殊世界状态。"
        lines = ["【世界状态】"]
        for key, value in self.world_state.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def get_world_model_for_prompt(self) -> str:
        """生成给 LLM 的世界模型说明文本"""
        if not self.world_model:
            return ""
        wm = self.world_model
        lines = [
            "【场景类型】" + wm.scenario_type,
            "【需要跟踪的世界状态】",
        ]
        for name, type_name in wm.world_state_schema.items():
            lines.append(f"- {name}（{type_name}）")
        if wm.event_types:
            lines.append("【本场景可能发生的事件类型】")
            lines.append(", ".join(wm.event_types))
        if wm.action_grammar:
            lines.append("【行动语义】")
            lines.append(wm.action_grammar)
        if wm.terminal_condition:
            lines.append(f"【终止条件】{wm.terminal_condition}")
        return "\n".join(lines)

    def check_terminal_condition(self) -> bool:
        """执行终止条件表达式，判断推演是否应结束"""
        # 默认兜底：达到设定回合数
        if self.current_round >= self.rounds:
            return True

        if not self.world_model or not self.world_model.terminal_condition:
            return False

        expr = self.world_model.terminal_condition.strip()
        if not expr:
            return False

        try:
            return self._eval_safe_expression(expr, self.world_state)
        except Exception:
            # 表达式解析失败时不阻断推演，仍按回合数兜底
            return False

    @staticmethod
    def _eval_safe_expression(expr: str, variables: dict[str, Any]) -> bool:
        """安全求值简单布尔/比较表达式

        支持：==, !=, <, <=, >, >=, and, or, not, in
        不支持：函数调用、属性访问、赋值等
        """
        allowed_operators = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.And: operator.and_,
            ast.Or: operator.or_,
            ast.Not: operator.not_,
            ast.In: lambda a, b: a in b,
            ast.Is: operator.is_,
            ast.IsNot: operator.is_not,
        }
        allowed_unary = {
            ast.Not: operator.not_,
            ast.USub: operator.neg,
        }

        node = ast.parse(expr, mode="eval")

        def _eval(n):
            if isinstance(n, ast.Expression):
                return _eval(n.body)
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.Name):
                if n.id in variables:
                    return variables[n.id]
                raise NameError(f"未定义的变量: {n.id}")
            if isinstance(n, ast.Compare):
                left = _eval(n.left)
                for op, comparator in zip(n.ops, n.comparators):
                    op_type = type(op)
                    if op_type not in allowed_operators:
                        raise ValueError(f"不支持的比较运算符: {op_type.__name__}")
                    right = _eval(comparator)
                    left = allowed_operators[op_type](left, right)
                return left
            if isinstance(n, ast.BoolOp):
                values = [_eval(v) for v in n.values]
                op_type = type(n.op)
                if op_type is ast.And:
                    return all(values)
                if op_type is ast.Or:
                    return any(values)
                raise ValueError(f"不支持的布尔运算符: {op_type.__name__}")
            if isinstance(n, ast.UnaryOp):
                operand = _eval(n.operand)
                op_type = type(n.op)
                if op_type not in allowed_unary:
                    raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
                return allowed_unary[op_type](operand)
            if isinstance(n, ast.BinOp):
                left = _eval(n.left)
                right = _eval(n.right)
                op_type = type(n.op)
                if op_type is ast.Add:
                    return left + right
                if op_type is ast.Sub:
                    return left - right
                raise ValueError(f"不支持的二元运算符: {op_type.__name__}")
            if isinstance(n, ast.List):
                return [_eval(elem) for elem in n.elts]
            if isinstance(n, ast.Tuple):
                return tuple(_eval(elem) for elem in n.elts)
            raise ValueError(f"不支持的表达式节点: {type(n).__name__}")

        return bool(_eval(node))

    def get_active_agents(self) -> list[Agent]:
        return [a for a in self.agents if a.is_actionable]

    def get_agent_by_id_or_name(self, identifier: str) -> Optional[Agent]:
        """按 ID 或名称查找 Agent"""
        if not identifier:
            return None
        # 先按 ID 匹配
        agent = next((a for a in self.agents if a.id == identifier), None)
        if agent:
            return agent
        # 再按名称匹配（忽略首尾空格）
        identifier = identifier.strip()
        return next((a for a in self.agents if a.name == identifier), None)

    def get_relation_by_id(self, relation_id: str) -> Optional[RelationEdge]:
        """按关系边ID查找"""
        return next((r for r in self.relations if r.id == relation_id), None)

    def find_relation(
        self, source_id: str, target_id: str, relation: str
    ) -> Optional[RelationEdge]:
        """按(source_id, target_id, relation)三元组查找关系边"""
        return next(
            (r for r in self.relations
             if r.source_id == source_id and r.target_id == target_id and r.relation == relation),
            None,
        )

    def get_relations_of(self, agent_id: str) -> list[RelationEdge]:
        return [r for r in self.relations if r.source_id == agent_id or r.target_id == agent_id]

    def get_outgoing_relations(self, agent_id: str) -> list[RelationEdge]:
        """获取某实体作为source的所有关系边"""
        return [r for r in self.relations if r.source_id == agent_id]

    def add_or_update_relation(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        description: str,
        current_round: int,
        polarity: str = "",
    ) -> RelationEdge:
        """按(source, target, relation)三元组查找，存在则更新，不存在则新建"""
        rel = self.find_relation(source_id, target_id, relation)
        if rel:
            rel.evolution_history.append({
                "round": current_round,
                "relation": rel.relation,
                "description": rel.description,
                "polarity": rel.polarity,
            })
            rel.description = description
            if polarity:
                rel.polarity = polarity
            rel.last_interaction_round = current_round
            rel.interaction_count += 1
        else:
            rel = RelationEdge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                description=description,
                polarity=polarity,
                created_round=current_round,
                last_interaction_round=current_round,
                interaction_count=1,
            )
            rel.evolution_history.append({
                "round": current_round,
                "relation": relation,
                "description": description,
                "polarity": polarity,
            })
            self.relations.append(rel)
        return rel

    def add_event(self, event: Event) -> None:
        self.events.append(event)
        if event.consequence_severity > 0.7:
            self.critical_nodes.append(event.round)
