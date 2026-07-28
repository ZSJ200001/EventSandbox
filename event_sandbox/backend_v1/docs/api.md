# EventSandbox API 文档 (v1)

## 基础信息

- **Base URL**: `http://localhost:8000`
- **API 前缀**: `/api`
- **Content-Type**: `application/json`

## 通用说明

### 错误响应格式

所有错误响应的 `detail` 字段包含人类可读的错误消息：

```json
{
  "detail": "错误描述信息"
}
```

| HTTP 状态码 | 含义 |
|------------|------|
| 400 | 请求参数错误（含业务异常） |
| 404 | 推演/Agent/任务不存在 |
| 423 | 推演正在执行中，暂不可操作 |
| 500 | 服务器内部错误 |

---

## 健康检查

### `GET /health`

检查服务状态。

**响应示例**：
```json
{
  "status": "healthy",
  "version": "1.1.0",
  "llm_connected": true,
  "llm_model": "Qwen3.6-27B",
  "simulation_count": 3,
  "timestamp": 1784000000000
}
```

---

## 推演管理

### `POST /api/simulations` — 创建推演（异步）

提交创建任务，立即返回 `task_id`。前端应轮询 `GET /api/simulations/create/{task_id}` 获取进度。

**请求体**：

```json
{
  "name": "推演名称",
  "description": "推演背景描述",
  "event_text": "初始事件描述（至少30字，详细描述效果更好）",
  "rounds": 10,
  "config": {
    "main_line": "推演主线问题，如：谁会赢得比赛？",
    "start_datetime": "2026-06-21T07:07:00",
    "round_duration_value": 1.0,
    "round_duration_unit": "day"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 推演名称 |
| `event_text` | string | 是 | 初始事件描述 |
| `description` | string | 否 | 推演背景描述 |
| `rounds` | int | 否 | 总回合数（1-100，默认10） |
| `config.main_line` | string | 否 | 推演主线问题 |
| `config.start_datetime` | string | 否 | 推演起始时间（ISO格式，默认当前时间） |
| `config.round_duration_value` | float | 否 | 每回合时长数值（≥0.1，默认1） |
| `config.round_duration_unit` | string | 否 | 时间单位：`round`/`minute`/`hour`/`day`/`week`/`month`/`quarter`/`year` |

**响应**（立即返回）：

```json
{
  "success": true,
  "message": "",
  "task_id": "a1b2c3d4",
  "status": "pending",
  "logs": [
    {"time": "13:07:15", "msg": "已提交创建任务: 美伊谈判推演"}
  ]
}
```

### `GET /api/simulations/create/{task_id}` — 查询创建进度

前端每 1.5 秒轮询此接口。`logs` 数组按时间顺序追加。

**响应示例**：

```json
{
  "success": true,
  "task_id": "a1b2c3d4",
  "status": "extracting_entities",
  "logs": [
    {"time": "13:07:15", "msg": "已提交创建任务: 美伊谈判推演"},
    {"time": "13:07:15", "msg": "开始构建推演图谱..."},
    {"time": "13:07:15", "msg": "正在提取事件实体..."},
    {"time": "13:07:22", "msg": "已提取 8 个实体: 美国, 伊朗, 卡塔尔, ..."},
    {"time": "13:07:22", "msg": "正在构建实体属性 (0/8)..."}
  ],
  "simulation": null,
  "error": "",
  "created_at": 1784000000.0,
  "updated_at": 1784000122.0
}
```

| `status` 值 | 说明 |
|-------------|------|
| `pending` | 已提交，等待执行 |
| `running` | 正在构建图谱 |
| `completed` | 创建成功，`simulation` 字段包含完整数据 |
| `failed` | 创建失败，`error` 字段包含错误信息 |

`completed` 时：`simulation` 字段为完整推演对象。前端可据此跳转到推演控制台，不再需要再次 `GET /api/simulations/{id}`。

---

### `GET /api/simulations` — 列出推演

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | 按状态过滤：`pending`/`running`/`paused`/`completed` |
| `limit` | int | 每页数量（默认20） |
| `offset` | int | 偏移量（默认0） |

**响应**：

```json
{
  "simulations": [
    {
      "id": "8b0189ca",
      "name": "美伊谈判推演",
      "description": "",
      "status": "running",
      "current_round": 5,
      "rounds": 10,
      "agent_count": 8,
      "event_count": 1
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### `GET /api/simulations/{simulation_id}` — 获取推演详情

返回完整的推演状态，含实体、事件、拓扑、指标、时间轴等。

**响应**（部分字段）：

```json
{
  "simulation": { "..." },
  "active_agent_count": 6,
  "event_count": 3,
  "recent_events": [],
  "agent_summaries": [
    {"id": "xxx", "name": "美国", "type": "government", "is_actionable": true, "sentiment": 0.35}
  ],
  "is_being_stepped": false
}
```

`is_being_stepped`：前端据此禁用推进按钮，并在 `true` 时每 2.5 秒轮询刷新。

---

### `DELETE /api/simulations/{simulation_id}` — 删除推演

**响应**：
```json
{"message": "推演已删除"}
```

---

## 回合推进

### `POST /api/simulations/{simulation_id}/step` — 执行一回合

所有可行动 Agent 并发决策，世界状态自动同步。

**请求体**：
```json
{
  "simulation_id": "8b0189ca",
  "intervention": null,
  "steps": 1
}
```

**响应**：
```json
{
  "simulation": { "..." },
  "new_events": [],
  "updated_agents": [],
  "action_results": [
    {
      "agent_id": "xxx",
      "agent_name": "美国",
      "action": "发表声明",
      "reasoning": "1. 局势感知: ...",
      "target_agents": ["伊朗"],
      "relation_changes": []
    }
  ],
  "round_summary": "第 1 回合完成"
}
```

### `POST /api/simulations/{simulation_id}/batch-step` — 批量推进

提交异步任务，立即返回任务信息。前端应轮询 `GET /api/simulations/{simulation_id}/batch-status/{task_id}`。

**请求体**：
```json
{
  "simulation_id": "8b0189ca",
  "steps": 5,
  "stop_on_condition": null,
  "conflict_threshold": 0.8
}
```

**响应**：
```json
{
  "task_id": "8b0189ca_a1b2c3d4",
  "simulation_id": "8b0189ca",
  "status": "pending",
  "steps_requested": 5,
  "steps_executed": 0,
  "events_generated": 0,
  "current_round": 0,
  "stop_reason": "",
  "error": ""
}
```

### `GET /api/simulations/{simulation_id}/batch-status/{task_id}` — 查询批量进度

**响应**：同上结构，`steps_executed` 实时更新。

---

## 事件注入

### `POST /api/simulations/{simulation_id}/events` — 注入外部事件

即刻生效，不推进回合。自动发现新实体、分析全局影响、更新关系。

**请求体**：
```json
{
  "description": "竞争对手宣布降价20%，市场格局生变"
}
```

**响应**：
```json
{
  "simulation": { "..." },
  "event": { "..." },
  "affected_agent_count": 3
}
```

---

## Agent 管理

### `GET /api/simulations/{simulation_id}/agents/{agent_id}` — Agent 详情

**响应**：
```json
{
  "agent": { "..." },
  "recent_memory": "格式化短期记忆",
  "relationship_summary": [],
  "action_history": [],
  "visible_actions": []
}
```

### `POST /api/simulations/{simulation_id}/agents/{agent_id}/modify` — 修改 Agent

**请求体**：
```json
{
  "simulation_id": "8b0189ca",
  "agent_id": "xxx",
  "field": "sentiment",
  "value": 0.5,
  "reason": ""
}
```

支持的 `field`：
| 值 | 说明 |
|----|------|
| `sentiment` | 情绪值（-1~1） |
| `description` | 角色描述 |
| `personality` | 性格标签 |
| `goals` | 目标列表 |
| `is_actionable` | 是否可行动 |
| `goal` | 追加单个目标 |

### `POST /api/simulations/{simulation_id}/agents` — 添加实体

自动调用 LLM 补全属性。

**请求体**：
```json
{
  "name": "新实体名称",
  "type": "individual",
  "description": "简要描述"
}
```

### `GET /api/simulations/{simulation_id}/agents/{agent_id}/actions` — 行动历史

**响应**：
```json
{
  "agent_id": "xxx",
  "agent_name": "美国",
  "total_actions": 10,
  "actions": []
}
```

---

## 推演控制

### `POST /api/simulations/{simulation_id}/pause` — 暂停

### `POST /api/simulations/{simulation_id}/resume` — 恢复

---

## 干预选项

### `GET /api/interventions/options` — 生成干预建议

LLM 根据当前推演场景生成干预选项。

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `simulation_id` | string | 推演 ID |
| `option_type` | string | 固定 `global` |
| `agent_id` | string | 暂未使用 |

**响应**：
```json
{
  "event_options": [
    {
      "key": "opt_0",
      "label": "选项标题",
      "description": "选项说明",
      "value": "可直接注入的完整描述"
    }
  ],
  "env_options": [],
  "option_type": "global",
  "generated": true
}
```

---

## 新闻检索

### `POST /api/news/search` — 向量检索相关新闻

使用 bge-m3 Embedding 在新闻库中检索与事件描述相似的新闻。

**请求体**：
```json
{
  "query": "美伊谈判取得突破",
  "topk": 10
}
```

**响应**：
```json
{
  "query": "美伊谈判取得突破",
  "total": 5,
  "results": [
    {
      "title": "新闻标题",
      "time": "2026-07-15",
      "keywords": "关键词",
      "description": "新闻摘要"
    }
  ]
}
```

---

## 报告生成

### `GET /api/simulations/{simulation_id}/report` — 获取已生成报告

返回推演报告（基于图谱）和基线报告（纯 LLM 线性推演）的组合。未生成时为 `null`。

**响应**：
```json
{
  "report": { "..." } | null,
  "baseline_report": { "..." } | null
}
```

### `POST /api/simulations/{simulation_id}/report` — 生成推演报告

基于图谱数据的五层报告：Agent 分析 → 整体局势 → 结论。生成后自动持久化。

### `POST /api/simulations/{simulation_id}/report/baseline` — 生成基线报告

纯 LLM 线性推演报告，基于初始输入完成。用于与图谱推演报告对比。

**请求体**（两个端点相同）：
```json
{}
```

**响应**（两个端点相同结构）：
```json
{
  "simulation_id": "8b0189ca",
  "title": "美伊谈判推演 推演分析报告",
  "agent_summaries": [
    {"agent_name": "美国", "summary": "行为分析文本..."}
  ],
  "overall_summary": "整体局势描述...",
  "conclusion": "结论文本...",
  "full_report": "完整 Markdown 报告..."
}
```

---

## 数据模型说明

### 时间切片配置

当 `round_duration_unit` 不为 `round` 时，推演具有时间语义：
- `current_simulated_time` 随回合推进自动更新
- Agent 决策和世界状态更新时，LLM 会感知当前模拟时间

### 关系边 (`RelationEdge`)

有向独立对象，每条关系边拥有唯一 `id`（8位十六进制）：
- `source_id` → `target_id`：A 对 B 的关系
- 同一对实体之间可以有多条不同 `relation` 标签的边
- `evolution_history` 记录每次变更快照
- `polarity`：`positive` / `negative` / `neutral` / `""`

### 拓扑结构 (`Topology`)

驱动前端 D3 图谱渲染：
- 节点类型：`agent` / `event`
- 边类型：`agent_relation`（Agent间关系）/ `event_affect`（事件影响）
