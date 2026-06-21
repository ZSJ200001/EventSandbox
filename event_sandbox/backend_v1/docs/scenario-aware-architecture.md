# EventSandbox 场景感知推演架构设计草案

> 记录时间：2026-06-16  
> 背景：当前关系驱动模型在足球比赛等事件密集型场景中表现不佳，需要讨论更通用的推演架构方向。  
> 状态：**已实现**（方案 C：混合方案）。

---

## 一、当前系统的核心假设与局限

### 1.1 核心假设

当前 `backend_v1` 采用**关系驱动推演模型**，其隐含假设是：

> 推演的核心价值在于 Agent 之间关系网络的演化。

因此系统设计围绕以下对象展开：
- `Agent`：具有性格、目标、情绪，每回合独立决策。
- `RelationEdge`：有向关系边，记录极性、标签、演变历史。
- `TimelineEntry`：记录 Agent 行动及其导致的关系变化。

Agent 每回合的输出被规范为：
```
action + relation_updates (+ environment_changes)
```

### 1.2 适用场景

该模型对以下场景效果较好：

| 场景类型 | 为什么合适 |
|---------|-----------|
| 地缘政治 | 核心产出就是联盟、对抗、制裁、谈判等关系变化 |
| 商业竞争 | 关键在于企业与消费者、监管者、竞争对手之间的动态关系 |
| 组织博弈 | 组织间的合作、背叛、影响力消长是主要观察对象 |

### 1.3 不适用场景

对以下场景效果较差：

| 场景类型 | 为什么不合适 |
|---------|-------------|
| 足球比赛 | 核心是比分、球权、时间、进球事件，关系变化只是副产品 |
| 军事战术 | 核心是兵力位置、伤亡、资源消耗、命令链，不是关系网络 |
| 灾害应急 | 核心是资源调度、伤亡数、响应时间，Agent 间关系不是重点 |
| 疾病传播 | 核心是感染数、传播路径、防控措施，Agent 关系几乎无关 |

### 1.4 足球推演暴露出的具体问题

以 `8294baf0.json`（西班牙 vs 佛得角）为例：

1. **没有时间边界感**：设 10 回合 × 15 分钟 = 150 分钟，但足球赛常规时间为 90 分钟。系统不知道何时该结束，Agent 一直生成进攻/防守动作。
2. **没有世界状态**：没有比分、球权、比赛阶段等状态，导致报告无法描述真实赛果。
3. **没有离散事件**：没有进球、犯规、换人、终场哨等事件，timeline 里只有战术动作和关系变化。
4. **行动没有后果**：Agent 输出“高位压迫”“边路渗透”，但系统不知道这些行动该改变什么状态。
5. **报告只能猜结论**：结论只能从“西班牙→佛得角：压制”这种关系中推断“西班牙会赢”，没有事实依据。

---

## 二、总体思路：把系统拆成两层

### 2.1 通用推演内核（领域无关）

负责所有不随场景变化的功能：
- 回合调度与并发锁
- LLM 客户端与并发调用
- Agent 记忆管理
- 持久化、API、路由
- 前端通信与状态同步
- 依赖注入与生命周期管理

### 2.2 场景世界模型（领域相关）

每个场景定义自己的：
- **世界状态（World State）**：需要被持续跟踪的变量
- **事件类型（Event Types）**：可能发生的离散事件
- **行动语义（Action Semantics）**：行动如何改变世界状态
- **终止条件（Terminal Condition）**：推演何时结束
- **胜负/结果判定（Outcome Evaluation）**：如何回答推演主线问题

| 维度 | 足球比赛 | 商业竞争 | 地缘政治 |
|---|---|---|---|
| 世界状态 | 比分、时间、球权、犯规数、换人名额 | 股价、市场份额、现金流、品牌声誉 | 冲突等级、协议状态、舆论倾向 |
| 事件类型 | 进球、犯规、红牌、角球、终场 | 并购、降价、产品发布、监管处罚 | 制裁、谈判破裂、军事冲突 |
| 行动语义 | 传球、射门、逼抢、换人、死守 | 降价、并购、研发、公关 | 威胁、妥协、结盟、制裁 |
| 终止条件 | 90 分钟 / 点球大战结束 | 达到目标份额 / 破产 | 战争爆发 / 签署协议 |
| 结果判定 | 比分高低 | 市场指标变化 | 目标达成度 |

---

## 三、三种可行实现方案

### 方案 A：场景模板（Scenario Template）

创建推演时，系统根据初始事件判断场景类型，加载预定义模板。

模板包含：
- `world_state_schema`：必须跟踪的状态字段
- `event_types`：合法事件类型
- `action_grammar`：行动的语义说明
- `terminal_condition`：终止条件表达式
- `report_template`：报告生成模板

**优点**：
- 稳定、可控、可解释
- 不同场景有专门优化

**缺点**：
- 每新增一个场景都要写模板
- 维护成本高
- 对“未见过”的场景适应性差

### 方案 B：完全由 LLM 生成世界模型

创建推演时，LLM 不只提取实体和关系，还要输出：
- 场景类型
- 世界状态变量
- 事件类型
- 终止条件
- 行动语义说明

推演过程中，Agent 每回合输出：
```json
{
  "action": "远射",
  "world_state_updates": {"possession": "西班牙"},
  "events": [{"type": "goal", "team": "西班牙", "minute": 67}],
  "relation_updates": []
}
```

引擎根据 LLM 生成的规则说明应用更新。

**优点**：
- 无需为每个场景写模板
- 高度灵活

**缺点**：
- 对 LLM 稳定性要求极高
- 终止条件、胜负判定等关键逻辑由 LLM 掌控，容易出错
- 难以调试和复现

### 方案 C：混合方案（推荐）

- **代码层**：维护通用的 `world_state: dict` 和 `events: list`，支持终止条件表达式。
- **LLM 层**：每个场景由 LLM 生成“世界模型说明”，告诉 Agent 这个场景有哪些状态、什么行动会改变它们、什么时候结束。
- **规则层**：终止条件、胜负判定等关键逻辑由代码执行，不由 LLM 自由发挥。
- **报告层**：基于 `world_state` 历史 + `events` 生成报告，而不是只基于关系变化。

**优点**：
- 兼顾灵活性和可控性
- 终止条件等关键逻辑由代码保证
- LLM 负责“理解场景”，代码负责“执行规则”

---

## 四、推荐的推演流程

如果采用方案 C，一次推演可分为三个阶段：

### 阶段 1：世界模型构建

输入初始事件后，LLM 输出场景世界模型：

```json
{
  "scenario_type": "football_match",
  "world_state_schema": {
    "score": "string",
    "match_phase": "enum:first_half,halftime,second_half,extra_time,full_time",
    "possession": "string",
    "fouls": "dict"
  },
  "event_types": ["goal", "foul", "substitution", "red_card", "full_time"],
  "terminal_condition": "match_phase == 'full_time'",
  "action_grammar": "每回合选择一个比赛动作，并说明对世界状态的影响",
  "initial_world_state": {
    "score": "西班牙 0:0 佛得角",
    "match_phase": "first_half",
    "possession": "西班牙",
    "fouls": {"西班牙": 0, "佛得角": 0}
  }
}
```

### 阶段 2：回合推演

每个 Agent 决策输出：

```json
{
  "action": "远射破门",
  "reasoning": "...",
  "world_state_updates": {
    "score": "西班牙 1:0 佛得角",
    "possession": "西班牙"
  },
  "events": [
    {"type": "goal", "team": "西班牙", "scorer": "佩德里", "minute": 67}
  ],
  "relation_updates": []
}
```

引擎执行：
1. 应用 `world_state_updates`
2. 追加 `events` 到事件日志
3. 应用 `relation_updates`（可选）
4. 检查 `terminal_condition`
5. 若满足终止条件，标记推演完成

### 阶段 3：报告生成

报告基于以下输入生成：
- 最终 `world_state`
- `events` 时间线
- Agent 行动记录
- 推演主线

示例足球报告结论：

> 第 67 分钟，佩德里远射破门，西班牙 1:0 领先。佛得角全场采取密集防守，未能组织有效反击。最终西班牙 1:0 获胜。

---

## 五、与当前架构的关系

### 5.1 保留什么

- 分层架构（Router → Service → Engine → Domain）
- 依赖注入
- 文件持久化
- 异步 LLM 并发
- Agent 记忆机制
- 报告生成引擎的基本框架

### 5.2 改变什么

| 当前 | 未来（已实现） |
|---|---|
| `Simulation.relations` 是一等公民 | `Simulation.world_state` 和 `Simulation.world_events_history` 与 `relations` 并列 |
| Agent 输出 `action + relation_updates` | Agent 输出 `action + world_state_updates + events + relation_updates` |
| Timeline 只记录关系变化 | Timeline 同时记录世界状态变化和事件（`world_event` 类型 TimelineEntry） |
| 时间切片只显示模拟时间 | 时间切片支持场景阶段和终止条件 |
| 报告基于关系史 | 报告基于世界状态史 + 事件史 |

## 六、实现细节

### 6.1 领域模型

新增 `core/domain/world_model.py`：

- `ScenarioWorldModel`：场景世界模型，包含 `scenario_type`、`world_state_schema`、`event_types`、`terminal_condition`、`action_grammar`、`initial_world_state`、`outcome_evaluation`。
- `WorldEvent`：离散事件，包含 `type`、`round`、`actor`、`description`、`metadata`。

`Simulation` 扩展字段：

- `world_model: ScenarioWorldModel | None` — 创建推演时由 LLM 自动生成。
- `world_state: dict` — 当前世界状态。
- `world_state_history: list[dict]` — 每回合世界状态快照。
- `world_events_history: list[WorldEvent]` — 离散事件历史。

### 6.2 世界模型生成

创建推演时，在关系提取之后新增一次 LLM 调用 `extract_world_model()`：

1. 输入初始事件描述和 Agent 列表。
2. LLM 输出 `ScenarioWorldModelOutput`。
3. 转换为 `ScenarioWorldModel` 保存到 `simulation.world_model`。
4. 初始化 `simulation.world_state = world_model.initial_world_state`。
5. 记录初始快照到 `world_state_history`。

### 6.3 Agent 决策与世界状态更新

`AgentDecisionOutput` 扩展字段：

- `world_state_updates: dict` — 本行动对世界状态的影响。
- `events: list[dict]` — 触发的离散事件。

`AgentEngine.apply_action_result()` 会：

1. 调用 `simulation.update_world_state(updates)` 应用状态更新。
2. 将 `events` 转换为 `WorldEvent` 并追加到 `world_events_history`。
3. 为事件生成 `world_event` 类型的 `TimelineEntry`。
4. 继续处理 `relation_updates` 和情绪变化。

### 6.4 终止条件

`Simulation.check_terminal_condition()` 使用 AST 白名单安全求值 `terminal_condition` 表达式：

- 支持 `==`、`!=`、`<`、`<=`、`>`、`>=`、`and`、`or`、`not`、`in`、`+`、`-`、列表、元组。
- 默认兜底：当 `current_round >= rounds` 时结束。
- 表达式解析失败时不阻断推演，按回合数兜底。

### 6.5 报告生成

`ReportEngine` 新增事实构建方法：

- `_build_world_state_facts()`：按回合整理世界状态变化。
- `_build_world_events_facts()`：按回合整理离散事件。
- `_build_timeline_facts()` 包含 `world_event` 类型条目。

整体总结和结论 Prompt 中注入世界状态历史和离散事件列表，要求结论必须基于最终 `world_state` 回答推演主线问题。

### 6.6 前端展示

- `SimulationView.vue` 顶部展示关键世界状态（如比分、比赛阶段、球权）。
- `ActionTimeline.vue` 支持 `world_event` 类型条目展示，包含事件元数据标签。

## 七、迁移路径建议

当前状态：**第一步至第四步已完成**，第五步（场景模板补充）仍为可选未来工作。

- 第一步：引入通用世界状态（已完成）。
- 第二步：场景世界模型自动生成（已完成）。
- 第三步：终止条件与阶段感知（已完成，`terminal_condition` 已支持）。
- 第四步：报告基于世界状态重写（已完成）。
- 第五步：场景模板补充（可选，尚未实现）。

---

## 八、关键结论

1. 当前系统不是“不能用于足球”，而是**关系驱动模型本身不是为事件密集型场景设计的**。
2. 真正通用的推演系统应该把 **Agent、关系、世界状态、事件、终止条件** 都作为一等公民。
3. 不同场景的差别在于这些要素的**权重不同**，而不是需要完全不同的系统。
4. 采用**混合方案**：代码负责状态执行和终止判断，LLM 负责场景理解与行动生成。
5. 报告从“关系演变史”升级为“世界状态演变史 + 事件史”。

---

## 九、待讨论问题

1. 是否需要为常见场景（足球、商业、地缘）提供可选模板？
2. 终止条件是否需要支持用户手动覆盖？
3. 是否需要支持世界状态变量的 UI 级编辑？
