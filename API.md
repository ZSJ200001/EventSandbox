# EventSandbox API 文档

> 后端版本：`backend_v1`（FastAPI）
> Base URL：`http://localhost:8000`
> 在线文档：`http://localhost:8000/docs`（Swagger UI）

---

## 通用说明

### 响应格式

所有 API 返回 JSON，成功时统一包装为：

```json
{
  "success": true,
  "message": "",
  // ... 业务字段
}
```

错误时返回 HTTP 状态码 + 错误详情：

```json
{
  "detail": "错误描述"
}
```

### 跨域配置

后端 CORS 配置为允许所有来源（`["*"]`），前端开发服务器可直接调用。

---

## 1. 健康检查

### GET `/health`

检查后端服务及 LLM 连接状态。

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态，`healthy` 或 `unhealthy` |
| `version` | string | 应用版本号 |
| `llm_connected` | bool | LLM API 是否可达 |
| `llm_model` | string | 当前使用的模型名称 |
| `simulation_count` | int | 内存中的推演总数 |
| `timestamp` | int | 时间戳（毫秒） |

---

## 2. 推演（Simulations）

前缀：`/api/simulations`

### POST `/api/simulations`

创建新推演。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 推演名称 |
| `description` | string | | 推演描述 |
| `event_text` | string | ✅ | 初始事件描述（自然语言） |
| `rounds` | int | | 总回合数，默认 10，范围 1-100 |
| `config` | object | | 推演配置，见 `SimulationConfig` |

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation` | Simulation | 完整推演对象（含生成的 agents、topology） |
| `generated_agents` | list[Agent] | 自动生成的实体列表 |
| `topology` | Topology | 初始拓扑结构 |

### GET `/api/simulations`

列出推演列表（支持分页和状态过滤）。

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | 按状态过滤：`pending` / `running` / `paused` / `completed` |
| `limit` | int | 每页数量，默认 20 |
| `offset` | int | 偏移量，默认 0 |

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulations` | list[SimulationSummary] | 推演摘要列表 |
| `total` | int | 总数 |
| `limit` | int | 每页数量 |
| `offset` | int | 当前偏移 |

`SimulationSummary` 字段：`id`, `name`, `description`, `status`, `current_round`, `rounds`, `agent_count`, `event_count`。

### GET `/api/simulations/{simulation_id}`

获取推演完整状态。

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation` | Simulation | 完整推演对象 |
| `active_agent_count` | int | 活跃实体数量 |
| `event_count` | int | 事件总数 |
| `recent_events` | list[Event] | 最近 20 条事件 |
| `agent_summaries` | list[dict] | 实体摘要列表（含 id/name/type/status/sentiment/goals_count/relationship_count） |

### POST `/api/simulations/{simulation_id}/step`

执行一回合推演。

> ⚠️ 纯回合推进，不再接受干预参数。干预请使用 `POST /events`。

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation` | Simulation | 更新后的推演对象 |
| `new_events` | list[Event] | 本回合新生成的事件 |
| `updated_agents` | list[Agent] | 状态有变化的实体 |
| `action_results` | list[dict] | 各 Agent 的行动结果 |
| `round_summary` | str | 本回合自动生成的摘要 |

### POST `/api/simulations/{simulation_id}/batch-step`

批量执行多回合。

**请求体**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation_id` | string | 推演 ID |
| `steps` | int | 执行回合数，默认 5，范围 1-50 |
| `stop_on_condition` | string | 停止条件（可选） |
| `sentiment_threshold` | float | 情绪阈值，默认 0.8 |
| `conflict_threshold` | float | 冲突阈值，默认 0.8 |

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation` | Simulation | 更新后的推演对象 |
| `steps_executed` | int | 实际执行回合数 |
| `events_generated` | list[Event] | 生成的事件列表 |
| `final_metrics` | SimulationMetrics | 最终指标 |
| `stop_reason` | str | 停止原因 |

### POST `/api/simulations/{simulation_id}/events`

注入外部事件 —— **即刻生效，不推进回合**。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `description` | string | ✅ | 事件自然语言描述 |

**执行流程**：
1. LLM 自动从描述中提取新实体并创建
2. LLM 全局影响分析，生成 `relation_updates` + `agent_logs`
3. 更新全局关系网络
4. 创建事件节点和 `event_affect` 边

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation` | Simulation | 更新后的推演对象 |
| `event` | Event | 新创建的事件 |
| `affected_agent_count` | int | 受影响的实体数量 |

### POST `/api/simulations/{simulation_id}/pause`

暂停推演。

**响应**：`{ simulation: Simulation, message: "推演已暂停" }`

### POST `/api/simulations/{simulation_id}/resume`

恢复推演。

**响应**：`{ simulation: Simulation, message: "推演已恢复" }`

### DELETE `/api/simulations/{simulation_id}`

删除推演（同时删除持久化文件）。

**响应**：`{ success: true, message: "推演已删除" }`

---

## 3. 实体（Agents）

前缀：`/api/simulations/{simulation_id}/agents`

### GET `/api/simulations/{simulation_id}/agents/{agent_id}`

获取实体详情。

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent` | Agent | 完整实体对象 |
| `recent_memory` | str | 近期记忆上下文 |
| `relationship_summary` | list[dict] | 关系摘要 |
| `action_history` | list[dict] | 行动历史 |
| `visible_actions` | list[dict] | 该实体可见的推演日志 |

### POST `/api/simulations/{simulation_id}/agents/{agent_id}/modify`

修改实体属性（即刻生效）。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `simulation_id` | string | ✅ | 推演 ID |
| `agent_id` | string | ✅ | 实体 ID |
| `field` | string | ✅ | 字段名：`status` / `sentiment` / `description` / `personality` / `goals` |
| `value` | any | ✅ | 新值 |
| `reason` | string | | 修改原因 |

**响应**：`{ agent: Agent, message: "成功修改 {field}" }`

### POST `/api/simulations/{simulation_id}/agents`

动态添加新实体。

> 添加后自动调用 LLM 补全 `description`、`personality`、`goals`、`attributes`、`keywords`。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 实体名称 |
| `type` | string | | 类型，默认 `individual` |
| `description` | string | | 初始描述 |

**响应**：`{ success: true, agent: Agent, message: "新角色「{name}」已添加", simulation: Simulation }`

### GET `/api/simulations/{simulation_id}/agents/{agent_id}/actions`

获取实体行动历史。

**响应**：`list[dict]`（行动记录列表）

---

## 4. 干预（Interventions）

前缀：`/api`

### GET `/api/interventions/options`

生成干预选项。

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `simulation_id` | string | 推演 ID |
| `option_type` | string | 选项类型，默认 `global` |
| `agent_id` | string | 目标实体 ID（可选，用于生成实体专属选项） |

**响应**：`{ event_options: [...], agent_options: [...], env_options: [...] }`

### POST `/api/interventions/quick`

快速干预 —— 直接注入预设事件，**不推进回合**。

**请求体**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation_id` | string | 推演 ID |
| `intervention_type` | string | 干预类型 |
| `quick_option` | string | 预设选项 key |
| `custom_value` | string | 自定义事件描述（可选，优先于 `quick_option`） |
| `target_agent_id` | string | 目标实体 ID（可选） |

**响应**：`{ success: true, message: "快速干预已应用" }`

---

## 5. 报告（Reports）

前缀：`/api/simulations/{simulation_id}`

### POST `/api/simulations/{simulation_id}/report`

生成推演报告（基于图谱的多 Agent 推演总结）。

**四层生成结构**：
1. 关键点提取（纯代码规则）
2. 逐 Agent 过程分析（并发 LLM，Top-5 核心 Agent）
3. 推演结果总结（单次 LLM）
4. 结论与建议（单次 LLM）

> 生成后自动持久化到 `simulation.report`。

**响应字段**：`GenerateReportResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `simulation_id` | string | 推演 ID |
| `title` | string | 报告标题 |
| `key_points` | list[KeyPoint] | 关键点列表 |
| `agent_summaries` | list[AgentSummary] | 逐 Agent 分析 |
| `overall_summary` | string | 整体局势分析 |
| `conclusion` | string | 结论与建议 |
| `full_report` | string | 完整 Markdown 报告 |

`KeyPoint` 字段：`round`, `type`, `agents`, `description`, `significance`

`AgentSummary` 字段：`agent_name`, `summary`

### POST `/api/simulations/{simulation_id}/report/baseline`

生成基线报告（纯 LLM 线性推演）。

> 基于初始输入，让单一 LLM 推演已发生的回合并生成分析报告。不涉及多 Agent 交互，用于与图谱推演报告进行对比。

> 生成后自动持久化到 `simulation.baseline_report`。

**响应**：同 `GenerateReportResponse`，`title` 标注为"基线预测报告（纯 LLM）"。

### GET `/api/simulations/{simulation_id}/report`

获取已生成的报告组合。

**响应**：`ReportBundleResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `report` | GenerateReportResponse \| null | 图谱推演报告 |
| `baseline_report` | GenerateReportResponse \| null | 基线报告 |

> 若两者都未生成，返回 404。

---

## 6. 检索（Retrieval）

前缀：`/api`

### POST `/api/news/search`

根据文本检索相关新闻（向量检索）。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 查询文本（事件描述） |
| `topk` | int | | 返回条数，默认 10，范围 1-50 |

**响应字段**：`SearchNewsResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | string | 查询文本 |
| `total` | int | 结果总数 |
| `results` | list[NewsItem] | 新闻列表 |

`NewsItem` 字段：`title`, `time`, `keywords`, `description`

---

## 附录：核心枚举值

### AgentType

`company`, `government`, `organization`, `individual`, `location`, `military`, `vehicle`, `entity`

### SimulationStatus

`pending`（待启动）, `running`（进行中）, `paused`（已暂停）, `completed`（已完成）

### 关系极性（polarity）

`positive`（友好/合作）, `negative`（对抗/冲突）, `neutral`（中立/一般往来）
