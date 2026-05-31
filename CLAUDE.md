# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在操作本仓库时的指引。

## 项目概述

EventSandbox（可干预的智能事件推演沙盘）是一款基于多智能体（Multi-Agent）架构的 AI 原生决策支持系统。用户以自然语言描述事件，系统自动提取实体、生成具备独立人格（基于大五人格模型）的 Agent，并驱动它们进行回合制推演演化。用户可在推演过程中进行三层实时干预：全局环境参数、单个 Agent 状态、以及外部事件注入。

## 常用命令

### 后端（FastAPI + Python 3.10+）

后端代码位于 `event_sandbox/backend/`。

```bash
cd event_sandbox/backend

# 启动开发服务器（热重载，端口 8000）
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用提供的启动脚本
./start.sh       # Linux/Mac
.\start.ps1      # Windows (PowerShell)
```

**关键环境变量**（详见 `.env.example`）：
- `LLM_API_BASE` — OpenAI 兼容接口地址（默认：`http://101.251.216.47/8411/v1`）
- `LLM_API_KEY`
- `DEFAULT_MODEL` — 默认：`Qwen3-Coder-Next`
- `PORT` — 默认：`8000`

依赖声明在 `pyproject.toml` 中，但运行时不强制检查；启动脚本会自动安装缺失的 `fastapi uvicorn pydantic httpx networkx`。

### 前端

本项目提供**两套前端实现**：

1. **独立 HTML 版**（`event_sandbox/frontend/index.html`）：
   - 纯原生 JS + D3，无需构建步骤。
   - API 地址从同目录 `config.js` 读取。
   - 直接用浏览器打开 `index.html` 即可使用。

2. **React + TypeScript 版**（`event_sandbox/frontend/src/`）：
   - 基于 Vite 构建。开发服务器会将 `/api` 代理到 `http://localhost:8000`。
   ```bash
   cd event_sandbox/frontend
   npm install
   npm run dev      # 端口 3000
   ```

## 架构说明

### 后端模块

- **`api/main.py`** — FastAPI 入口。定义 `/api` 与 `/health` 等端点。通过 lifespan 上下文持有全局唯一的 `SimulationEngine` 实例。
- **`core/simulation/engine.py`** — `SimulationEngine` 是核心调度器。所有活跃推演保存在内存字典 `self.simulations` 中，负责调度 Agent 回合、处理干预、计算指标、批量推进及场景对比。
- **`core/agent/engine.py`** — `AgentEngine` 负责单个 Agent 的决策与行动。它构建包含人格、记忆、关系、近期事件的丰富上下文，调用 LLM 进行 `decide_action()`，然后将行动结果转化为事件、更新情绪值与关系强度。
- **`core/event_parser/parser.py`** — `EventParser` 利用 LLM 从自由文本中提取实体与关系，自动生成带有个性化设定的 `Agent` 对象。
- **`core/knowledge/graph.py`** — `KnowledgeGraph`（基于 NetworkX）维护类型层级与关系约束。例如，竞争关系的 Agent 不能执行"合作"类行动。
- **`core/llm.py`** — 唯一的 LLM 集成点。实现了自动重试（`@retry_on_failure`）、Few-shot 示例注入，以及多层 JSON 解析容错（直接解析 → Markdown 代码块提取 → 花括号提取）。
- **`models/entities.py`** — 核心 Pydantic 模型。关键结构：`Simulation`、`Agent`（含 `PersonalityTraits`、`AgentMemory`、`Belief`、`Relationship`）、`Event`、`Intervention`、`Topology`。
- **`models/schemas.py`** — 各 API 端点的请求/响应 Pydantic Schema。

### 单回合数据流

1. `POST /api/simulations/{id}/step`
2. `SimulationEngine.step()` 增加回合数，应用待处理的干预，然后遍历所有活跃 Agent。
3. 对每个 Agent：
   - `AgentEngine.build_situation_summary()` 整合人格、记忆、信念与近期事件。
   - `LLMClient.decide_action()` 返回包含 `action`、`reasoning`、`target_agents`、`sentiment_change` 等的 JSON。
   - `AgentEngine.apply_action_result()` 创建 `Event`、更新情绪、调整关系强度、记录 `MemoryEntry`，并视情况触发连锁反应。
   - `KnowledgeGraph.validate_action()` 若行动违反关系约束，会在事件描述前标注 `[受限]`。
4. `SimulationEngine._update_metrics()` 重新计算 `overall_sentiment`、`market_activity`、`cooperation_level`、`conflict_level`、`stability`、`innovation`。
5. 返回更新后的推演状态与新生成的事件。

### 前端状态管理

- React 前端使用 **Zustand**（`src/stores/simulationStore.ts`）管理全局状态。
- `API_BASE = '/api'`（由 Vite 开发服务器代理）；独立 HTML 版则通过 `window.EVENT_SANDBOX_CONFIG` 拼接完整 URL。

## 关键实现细节

- **无持久化存储** — 推演、Agent、事件全部保存在 `SimulationEngine.simulations` 内存中。重启后端后所有状态丢失。
- **LLM JSON 容错** — `LLMClient._parse_json_response()` 是关键路径。若修改提示词格式，需确保 JSON 仍能通过三层回退解析。
- **Agent 记忆机制** — `AgentMemory` 维护短期记忆（最多 20 条），溢出时将重要性最高的 3 条归档至长期记忆。仅短期记忆会被送入 LLM 上下文。
- **干预类型**（`entities.py`）：
  - `GLOBAL_PARAM` — 修改 `simulation.market_conditions` 或 `global_sentiment`
  - `AGENT_STATE` — 向指定 Agent 注入信念、改变情绪或添加目标
  - `EXTERNAL_EVENT` — 创建类型为 `EXTERNAL` 的事件
  - `ADD_AGENT` / `REMOVE_AGENT` / `MODIFY_RELATION` — 结构性变更
- **场景对比端点**（`POST /api/simulations/{id}/compare`）会直接在当前推演对象上先执行带干预的若干回合，再与基线对比。调用该接口会改变推演状态。
- **跨域** — `api/main.py` 中 CORS 配置为允许所有来源（`["*"]`）。

## 测试与质量

目前项目中没有测试套件。`pyproject.toml` 已将 `pytest`、`pytest-asyncio`、`black`、`ruff` 列为可选开发依赖，但尚未实际启用。

## 代码风格提示

- 后端使用 Pydantic v2（`BaseModel`、`Field`、`model_dump()`）。
- 部分模块顶部存在 `sys.path` 注入，以便直接运行脚本；在正确的包上下文中工作时可忽略。
- 独立 HTML 前端（`index.html`）是单个约 900 行的内联 CSS + 原生 JS 文件。React 组件基本复现了相同的功能结构。
