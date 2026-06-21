# EventSandbox 报告生成路线图

> 本文件记录报告生成环节的实现计划。前置依赖（统一时间轴 `timeline`）已完成。

---

## 总体目标

基于已构建的统一推演日志，生成一份紧扣推演主线的结构化分析报告。

## 三层报告结构

| 层级 | 名称 | 生成方式 | 输入数据 |
|------|------|---------|---------|
| 第一层 | 逐 Agent 过程分析 | **多次 LLM 调用**（每个核心 Agent 一次） | `timeline` 中按 Agent 分组的客观行动与关系变化 |
| 第二层 | 整体局势描述 | **一次 LLM 调用** | 按回合整理的 `timeline` 关键事实 |
| 第三层 | 结论 | **一次 LLM 调用** | 推演主线 + 初始事件 + 整体局势描述 |

已移除的环节：关键点提取、局势演变脉络。

---

## 第一层：逐 Agent 过程分析（多次 LLM 调用）

### 目标
为每个核心 Agent（有实际行动的 Top-5）生成独立的行为小结。

### Prompt 输入
- Agent 基本信息（名称、类型、性格、目标）
- 该 Agent 的客观行动记录（按回合排序，不含情绪指标）
- 涉及该 Agent 的关系变化清单（从 `timeline` 中提取）

### Prompt 要求
```
请基于以下角色的客观行动记录和关系变化，撰写行为小结（200字以内）：
1. 按回合顺序列出该角色采取的主要行动
2. 列出该角色与其他角色之间发生的关系变化
3. 不要分析情绪、性格或“对主线推进的作用”
```

### 输出
每个 Agent 一段文本，汇总为 `agent_summaries: list[AgentSummary]`。

---

## 第二层：整体局势描述（一次 LLM 调用）

### 目标
按回合顺序客观描述推演中发生的主要事实和关系变化。

### Prompt 输入
- 推演概况（回合数、Agent 数、事件数）
- 按回合整理的 `timeline` 关键事实（外部事件、新增实体、关系变化）

### Prompt 要求
```
请基于以下事实材料，按回合顺序撰写整体局势描述（400字以内）：
1. 严格按回合顺序描述实际发生的事件和关系变化
2. 只描述具体事实，不要总结“趋势”“脉络”“结构”“模式”
3. 不要推断事实材料中未出现的信息
```

### 输出
一段客观局势描述文本 `overall_summary`。

---

## 第三层：结论（一次 LLM 调用）

### 目标
直接回答推演主线提出的问题，而不是对推演过程做泛泛总结。

### Prompt 输入
- 推演主线 `simulation.config.main_line`
- 初始事件描述
- 第二层整体局势描述
- 关键事实列表

### Prompt 要求
```
请基于以上客观事实和整体局势描述，直接回答推演主线提出的问题（200字以内）：
1. 结论必须紧扣推演主线
2. 只使用已描述的事实作为论据，不要引入新信息
3. 不要给出泛泛的战略建议或总结普遍规律
```

### 输出
一段精炼结论文本 `conclusion`。

---

## 后端实现

### 相关文件

| 文件 | 职责 |
|------|------|
| `engines/report_engine.py` | `ReportEngine` / `BaselineReportEngine`，封装三层生成逻辑 |
| `schemas/report_responses.py` | `GenerateReportResponse`、`ReportBundleResponse` |
| `app/routers/reports.py` | 报告生成与获取路由 |
| `infrastructure/llm/prompts.py` | 报告相关 Prompt 模板 |

### API 设计

```
POST /api/simulations/{simulation_id}/report
Response: {
    "simulation_id": "...",
    "title": "推演报告",
    "agent_summaries": [{"agent_name": "...", "summary": "..."}],
    "overall_summary": "...",
    "conclusion": "...",
    "full_report": "# Markdown 完整报告"
}
```

---

## 前端实现

### 相关文件

| 文件 | 修改内容 |
|------|---------|
| `src/api/index.js` | `generateReport(simulationId)`、`generateBaselineReport(simulationId)` |
| `src/views/SimulationView.vue` | “生成报告”按钮与面板控制 |
| `src/components/ReportPanel.vue` | 以 Tab 展示报告三层内容：Agent 分析、整体总结、结论、完整报告 |

### 交互流程
1. 用户在推演界面点击“生成报告”
2. 前端调用 `POST /api/simulations/{id}/report`
3. 后端依次执行三层生成（逐 Agent 分析 → 整体局势描述 → 结论）
4. 返回完整报告 JSON
5. 前端以 Tab 形式展示：Agent 分析 / 整体总结 / 结论 / 完整报告

---

## 风险与注意事项

1. **LLM 调用成本**：第一层逐 Agent 分析会发起最多 5 次 LLM 调用。
2. **上下文长度**：第二层输入包含按回合整理的关键事实，长推演需控制长度。
3. **生成耗时**：三层全部走 LLM 可能需要 15-40 秒，前端需展示 Loading 状态。
4. **缓存策略**：同一推演同一回合的报告结果可缓存，避免重复生成。
