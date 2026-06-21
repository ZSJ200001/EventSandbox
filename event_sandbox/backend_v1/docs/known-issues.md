# 已知问题

本文档记录当前已发现但尚未修复的问题，按发现时间倒序排列。

---

## 1. LLM 关系提取偶尔返回错误格式导致 Pydantic 校验失败

**发现时间**：2026-06-17
**影响范围**：`RelationshipExtractionOutput.event_relations`
**状态**：已记录，暂不修复

### 现象

创建推演时，`extract_relationships()` 偶发报错：

```
1 validation error for RelationshipExtractionOutput
event_relations.9
  Input should be a valid dictionary or instance of EventRelation [type=model_type, input_value=['target'], input_type=list]
```

### 原因

LLM 未严格遵守 `event_relations` 的 JSON Schema。模型期望每个条目是 `EventRelation` 对象（字典），但 LLM 偶尔返回列表形式，例如 `["target"]` 而不是 `{ "agent_id": "...", "role": "target", ... }`。

这是 LLM 输出不稳定的偶发问题，非代码逻辑 bug。

### 临时处理

- 换一条初始事件描述重新创建推演。
- 避免触发 LLM 对短列表/角色的歧义理解。

### 未来修复方向

在 `extract_relationships()` 中对 `event_relations` 做前置脏数据清洗：
- 过滤掉非字典项。
- 或将类似 `["target"]` 的列表转换为 `{ "role": "target" }` 的合法对象后再进行 `model_validate()`。

---

## 2. batch-step 请求与正在执行的 step 冲突导致 StepLockedError

**发现时间**：2026-06-17
**影响范围**：`POST /api/simulations/{id}/batch-step`
**状态**：已记录，暂不修复

### 现象

调用 batch-step 时，第一回合就抛出 `StepLockedError`：

```
[SimulationEngine] step 被锁定, simulation_id=5baa1d2c
StepLockedError: 推演 5baa1d2c 正在进行中，请稍后再试
```

### 原因分析

`SimulationEngine` 为每个推演维护一个 `asyncio.Lock`，防止同一推演被并发推进。当前一个 step（或 batch-step）尚未完成时，新的 batch-step 请求到达，就会因为无法获取锁而失败。

从日志可见：
1. `10:38:04,053` 引擎已开始进入第 5 回合（某个 step/batch-step 正在执行）。
2. `10:38:04,483` 收到 `batch-step` 请求。
3. 此时上一轮 step 仍在执行，锁未释放，新请求被拦截。

**注意**：前端按钮确实已使用 `isLoading` 禁用推进按钮，但仍有多种场景可能绕过前端保护：

1. **页面刷新 / 路由切换后返回**：`batch-step` 可能持续数十秒（5 回合 × 8 Agent × LLM 延迟），期间如果用户刷新页面或切换到其他路由再返回，`store.isLoading` 会被重置为 `false`，按钮重新变为可用，但后端仍在执行之前的 batch。
2. **多浏览器标签页**：状态是每个标签页独立的，一个标签页发起 batch-step 后，另一个标签页仍可点击推进。
3. **极速双击**：Vue 的 DOM 更新是异步的，理论上存在用户连续两次点击都触发 `handleBatchStep` 的窗口期（实际概率较低）。
4. **前端网络层重试**：`api/index.js` 的 `requestWithRetry` 会对包括 `StepLockedError`（HTTP 400）在内的所有失败进行最多 3 次重试，重试期间锁可能仍未释放，导致多次报错。

### 临时处理

- 等待当前回合 / 批量推演执行完成后再发起 batch-step。
- 避免在批量推演过程中刷新页面或打开多个标签页同时操作同一个推演。
- 单步推进与批量推进不要同时触发。

### 未来修复方向

可选方案（按推荐程度排序）：

1. **后端排队机制（推荐）**：`batch-step` 发现锁被占用时，不直接报错，而是将请求放入队列，等锁释放后串行执行。返回时可告知用户"已排队，等待当前推演结束"。
2. **后端轮询等待**：`batch-step` 获取锁时增加短暂等待（如最多等 5 秒），而不是立即失败，给正在执行的回合一个收尾机会。
3. **前端状态持久化 / 恢复**：页面刷新后，通过查询后端状态判断是否有正在执行的 step，若有则保持按钮禁用。
4. **细化重试策略**：让 `requestWithRetry` 对 `StepLockedError` 使用更短的退避或更少的重试次数，避免无效重试放大问题。
5. **操作前二次确认**：当检测到后端正在执行时，前端弹出提示"推演进行中，是否等待完成后继续？"，将决定权交给用户。

**已实施（2026-06-17）**：方案 3 和方案 4 已落地。
- 后端 `GET /api/simulations/{id}` 响应新增 `is_being_stepped` 字段，前端按钮据此禁用并显示"推演进行中..."。
- 当 `is_being_stepped=true` 时，前端每 2.5 秒轮询刷新，直到后端执行完成。
- `StepLockedError` 改为返回 HTTP 423，前端 `requestWithRetry` 识别后不再重试。

**剩余限制**：同一推演的多个浏览器标签页仍可能在极短时间内同时点击推进（race window 毫秒级）。如需彻底杜绝，需实施后端的排队或等待机制（方案 1/2）。

---
