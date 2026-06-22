# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在操作本仓库时的指引。

## 项目概述

EventSandbox（可干预的智能事件推演沙盘）是一款基于多智能体（Multi-Agent）架构的 AI 原生决策支持系统。用户以自然语言描述事件，系统自动提取实体、生成具备独立人格的 Agent，并驱动它们进行回合制推演演化。推演过程中用户可随时**注入外部事件**（LLM 自动分析影响并更新关系网络），或在 Agent 详情面板中**编辑实体属性**，干预与回合推进完全分离。

## 核心架构理念（关系驱动推演）

本系统采用**关系驱动**的图谱演化模型，而非传统的事件节点堆积模型：

- **Agent 自主行动不创建事件节点** —— 行动结果体现为 Agent 之间关系边的语义更新
- **LLM 分布式语义更新** —— 每个 Agent 在决策时输出 `relation_updates`，代码只负责执行写入
- **全局关系统一管理** —— 所有关系边存储在 `Simulation.relations` 中，不挂在任何 Agent 下
- **有向边独立对象** —— 每条关系边是独立对象，含自身 `id`；A→B 和 B→A 是两条不同的边
- **多关系支持** —— 同一对 `(source, target)` 之间可以有多个不同 `relation` 标签的边
- **关系边短 ID** —— Agent、Event、Simulation、RelationEdge 均采用 8 位十六进制短 ID，便于 LLM 引用
- **双向语义独立** —— A→B 和 B→A 可以是完全不同的关系标签和描述
- **自然语言描述替代量化强度** —— 关系边带有 `description` 字段记录演变过程
- **演变历史可追溯** —— 关系边 `evolution_history` 记录每次变更后的完整快照，支持历史回放

## 常用命令

### 后端（FastAPI + Python 3.10+）

后端位于 `event_sandbox/backend_v1/`，采用分层架构。

```bash
cd event_sandbox/backend_v1

# 启动开发服务器（热重载，端口 8000，自动使用项目 .venv）
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用提供的启动脚本
./start.sh       # Linux/Mac
.\start.ps1      # Windows (PowerShell)
```

**关键特性**：
- **异步 LLM 并发**：一回合内所有 Agent 决策通过 `asyncio.gather` 并行发出
- **清晰分层**：Router → Service → Engine → Domain，单向依赖
- **依赖注入**：全部通过 FastAPI `Depends` 注入，消灭全局变量
- **统一配置**：`pydantic-settings` 单点管理环境变量
- **Repository 模式**：`FileBasedSimulationRepository` 文件持久化实现，重启不丢失数据，内存按需加载
- **异常体系**：自定义业务异常 + 全局异常处理器，统一返回格式
- **结构化日志**：所有操作带时间戳，报错直接体现在日志中
- **容错机制**：单个 Agent 决策失败不影响其他 Agent，自动 fallback 到观望
- **uv 环境**：项目使用 `uv` 管理 Python 依赖，启动脚本通过 `uv run` 自动激活 `.venv`

**目录结构**：
```
backend_v1/
├── app/               # FastAPI 应用层（路由、依赖注入、全局异常）
├── core/              # 业务核心（配置、异常、领域模型）
├── engines/           # 推演引擎（SimulationEngine、AgentEngine、BaselineReportEngine）
├── services/          # 业务服务层（SimulationService、AgentService、InterventionService）
├── infrastructure/    # 基础设施（LLM Client、持久化、事件总线）
├── schemas/           # API 输入输出 Pydantic 模型
└── tests/             # 测试套件（pytest + pytest-asyncio）
```

**关键环境变量**（详见 `.env.example`）：
- `LLM_API_BASE` — OpenAI 兼容接口地址（默认：`http://101.251.216.47/8411/v1`）
- `LLM_API_KEY`
- `DEFAULT_MODEL` — 默认：`Qwen3-Coder-Next`
- `PORT` — 默认：`8000`

依赖声明在 `pyproject.toml` 中，使用 `uv` 管理。首次设置执行 `uv sync` 即可自动创建 `.venv` 并安装全部依赖。启动脚本通过 `uv run` 自动激活项目虚拟环境。

### 前端

前端位于 `event_sandbox/frontend_v1/`，基于 Vue 3 Composition API + Vite 构建，从 MiroFish 项目迁移并深度适配。

- **D3 力导向图谱**：复用 MiroFish 的高质量图谱组件（曲线边、自环、缩放、拖拽、详情面板）。
- **三态布局切换**：图谱 / 分栏 / 工作台三种视图模式。
- **System Logs 控制台**：底部黑底日志面板，实时展示后端操作记录。
- **推演控制台**：集成指标仪表盘、实体列表、推演时间轴、干预面板、Agent 详情弹窗。
- **干预面板**：只保留"事件注入"和"添加实体"两项。事件注入支持文本描述输入 + "生成建议"按钮（调用 LLM 生成预设选项）+ "检索相关新闻"按钮（向量检索真实新闻作为灵感），注入后立即生效，不推进回合。添加实体自动调用后端 LLM 补全属性。
- **推演时间轴**：展示 `simulation.timeline` 中的全部推演日志，包括 Agent 行动（粉红色）、外部事件注入（橙色）、新增实体（绿色），支持关系变更的 `before/after` 展示。每条记录头部显示 `R{round}` 回合徽章，明确标注事件发生的回合。
- **推演报告面板**：点击"生成报告 ▼"下拉菜单可选择生成推演报告（基于图谱）、生成基线报告（纯 LLM）或同时生成两者。推演报告为五层结构（关键点→局势演变脉络→Agent 分析→整体总结→结论），基线报告为同构的单 LLM 线性推演。两份报告均自动持久化。当两份报告都存在时，Panel 内显示视图切换栏（推演报告 / 基线报告 / 对比），默认单栏展示，点击"对比"进入左右分栏。支持 5 个 Tab 切换（关键点 / Agent 分析 / 整体总结 / 结论 / 完整 Markdown），完整报告使用 `marked` 库渲染 Markdown 语法。
- **Agent 详情弹窗**：点击节点或实体列表打开，展示完整信息（可行动、情绪、描述、性格、目标、记忆、事件日志、关系）。事件日志以多行卡片形式展示，包含 `content`（行动描述）和 `reasoning`（决策推理），支持"编辑"模式：修改情绪（数值）、描述、性格、目标（数组增删）、**可行动（复选框）**，保存后即刻生效。
- 开发服务器将 `/api` 与 `/health` 代理到 `http://localhost:8000`。

```bash
cd event_sandbox/frontend_v1
npm install
npm run dev      # 端口 3000
```

## 架构说明

### 后端模块（backend_v1）

#### 应用层（app/）
- **`app/main.py`** — FastAPI 入口。负责日志配置、全局异常处理、lifespan 管理、CORS、路由挂载。
- **`app/dependencies.py`** — 依赖注入容器。通过 `lifespan_init()` / `lifespan_shutdown()` 管理 `AsyncLLMClient`、`SimulationEngine`、各 `Service` 的生命周期，消灭全局变量。
- **`app/routers/`** — 按资源拆分的路由模块：
  - `simulations.py` — 推演 CRUD、step（纯推进，不处理干预）、batch-step（已移除 `sentiment_threshold` 停止条件）、事件注入（`POST /events`）、暂停/恢复/删除
  - `agents.py` — Agent 详情、修改、添加、行动历史
  - `interventions.py` — 干预选项生成（`GET /interventions/options`）、快速干预（`POST /interventions/quick`，改造为直接注入事件，不推进回合）
  - `retrieval.py` — 新闻向量检索（`POST /news/search`）
  - `reports.py` — 推演报告生成（`POST /api/simulations/{id}/report` 生成图谱推演报告、`POST /api/simulations/{id}/report/baseline` 生成纯 LLM 基线报告、`GET /api/simulations/{id}/report` 获取报告组合 `{report, baseline_report}`）
  - `health.py` — 健康检查

#### 业务核心（core/）
- **`core/config.py`** — `pydantic-settings` 统一配置。集中管理 LLM、推演、日志、**实体构建并发数**等全部环境变量。
- **`core/exceptions.py`** — 业务异常体系。`EventSandboxError` 基类及其子类（`SimulationNotFoundError`、`StepLockedError`、`LLMError` 等），由全局异常处理器统一转换为 HTTP 响应。
- **`core/domain/`** — 纯净领域模型（Pydantic v2），无业务逻辑，无 FastAPI 依赖：
  - `simulation.py` — `Simulation`、`SimulationConfig`、`SimulationMetrics`、`Topology`。`SimulationConfig` 新增**时间切片配置**（`start_datetime`、`round_duration_value`、`round_duration_unit`），支持为推演设置起始时间和每回合代表的真实时长；`Simulation` 新增 `current_simulated_time` 字段，回合推进时自动同步。`Simulation` 包含 `report`（图谱推演报告）和 `baseline_report`（纯 LLM 基线报告）两个持久化字段。
  - `agent.py` — `Agent`、`AgentMemory`、`MemoryEntry`
  - `event.py` — `Event`、`EventImpact`
  - `relation.py` — `RelationEdge`。每条关系边是有向独立对象，含 `id`、`source_id`、`target_id`、`relation`、`description`、`polarity`、`created_round`、`last_interaction_round`、`interaction_count`、`evolution_history`。
  - `common.py` — 枚举定义（`AgentType`、`SimulationStatus`、`InterventionType` 等）。`AgentStatus` 已删除，Agent 不再维护独立状态机。

**Agent 模型精简说明**：`Agent` 已去掉冗余字段（`deep_profile`、`current_strategy`、`personality_traits` 大五人格、`beliefs`、`resources`、`position_x/y`、`status`）。`AgentStatus` 枚举（ACTIVE/INACTIVE/INTERVENED/ELIMINATED）已整体删除，Agent 不再维护独立状态机，仅通过 `is_actionable: bool` 区分是否参与回合决策。`is_actionable` 由 LLM 在初始构建时根据实体类型和上下文语义判定，**用户可在 Agent 详情面板编辑并即时生效**。保留精简字段集：`description`（人设描述）、`personality`（性格标签字符串）、`sentiment`（顶层情绪值 -1~1）、`attributes`（动态属性字典）、`keywords`（关键词标签）、`is_actionable`（是否可行动）、`controller_id`（控制者）。LLM 对自然语言性格标签的理解远好于抽象数字分数。

#### 推演引擎（engines/）
- **`engines/simulation_engine.py`** — 核心调度器。使用 `asyncio.Lock` 替代 `threading.Lock`，与 FastAPI 异步模型一致。负责创建推演、`inject_event()`（事件注入，自动发现新实体并分析影响）、回合调度、拓扑同步、指标计算、批量推进。**全局关系边存储在 `simulation.relations` 中。回合推进时自动更新 `current_simulated_time`。**
- **`engines/agent_engine.py`** — 单 Agent 决策与行动应用。构建人格/记忆/关系/事件/时间上下文，调用 LLM 进行 `decide_action()`。LLM 返回的 `relation_updates` 和 `self_log` 写入全局关系和 Agent 日志。每个 `relation_update` 只操作当前 Agent 作为 source 的一条有向边。**Agent 行动不创建事件节点。**
- **`engines/report_engine.py`** — 报告生成引擎，包含两套实现：`ReportEngine`（基于图谱推演的三层报告：逐 Agent 分析 → 整体局势描述 → 结论）和 `BaselineReportEngine`（基于初始输入的纯 LLM 线性推演报告，输出同构结构用于对比）。报告不再输出关键点和局势演变脉络；结论必须直接回答推演主线提出的问题，而不是对推演过程做泛泛总结。

#### 业务服务层（services/）
- **`services/simulation_service.py`** — 推演用例编排。封装创建、step、batch、暂停/恢复等操作，参数校验前置。
- **`services/agent_service.py`** — Agent 用例编排。封装详情查询、状态修改（`modify()` 调用 `repo.save()` 持久化）、动态添加（`add_agent()` 自动调用 LLM 补全属性）等操作。
- **`services/intervention_service.py`** — 干预用例编排。封装快速干预、干预选项生成等操作。

#### 基础设施（infrastructure/）
- **`infrastructure/llm/client.py`** — `AsyncLLMClient`。基于 `httpx.AsyncClient`，支持异步并发、自动重试（指数退避）、多层 JSON 解析容错。
- **`infrastructure/llm/prompts.py`** — 所有提示词模板与 Few-shot 示例集中管理。
- **`infrastructure/llm/schemas.py`** — LLM 输入输出的 Pydantic 结构化模型。
- **`infrastructure/persistence/file.py`** — `FileBasedSimulationRepository` 文件持久化实现。每个推演保存为 `data/simulations/{id}.json`，启动时自动恢复；内存中仅保留轻量摘要（id/name/status/round/agent_count/event_count），完整数据按需从磁盘加载，避免推演数量增多导致内存膨胀。
- **`infrastructure/event_bus.py`** — 内存异步事件总线（预留解耦用）。

#### API 模型（schemas/）
- **`schemas/requests.py`** — 请求体 Pydantic 模型
- **`schemas/responses.py`** — 响应体 Pydantic 模型

### 单回合数据流（backend_v1）

**干预与推进完全分离**后的流程：

#### 事件注入（独立接口，即刻生效）

`POST /api/simulations/{id}/events`

1. `SimulationEngine.inject_event()` 执行：
   - **LLM 自动发现新实体**：调用 `extract_entities()` 从事件描述中提取涉及实体；不在推演中的实体自动创建（调用 `build_agent_attributes()` 补全 description、personality、goals 等属性），同时创建 `TopologyNode`
   - 创建 `Event(type=EXTERNAL)` 并加入 `simulation.events`
   - **LLM 全局影响分析**：调用 `analyze_external_impact()`，传入当前所有实体（含刚创建的），返回 `relation_updates` + `agent_logs`
   - **ID 解析容错**：`relation_updates` 和 `agent_logs` 中的 `source_id`/`target_id`/`agent_id` 支持**ID 或实体名称**双匹配（`_resolve_agent_id()`）
   - 应用关系更新到 `simulation.relations`，写入各 agent 的 `event_log`
   - 创建 `TopologyNode(node_type="event")` 和 `TopologyEdge(edge_type="event_affect")` 连接事件节点与所有受影响实体
   - `_sync_relations_to_topology()` + `_update_metrics()` + `repo.save()`
2. 返回完整 `Simulation`，前端立即刷新图谱（回合数**不推进**）

#### 回合推进（不再处理干预）

`POST /api/simulations/{id}/step`

1. `SimulationService.step()` → `SimulationEngine.step()` 增加回合数（**不再传入或处理干预**）
2. **并行决策**：使用 `asyncio.gather` 并发调用所有**可行动**（`is_actionable=True`）Agent 的 `decide_action()`：
   - 不可行动实体（地点、载具等）保留在图谱中，但不调用 LLM 决策
   - `AgentEngine.build_situation_summary()` 整合 `description`、`personality`、`sentiment`、记忆与关系上下文
   - `AsyncLLMClient.decide_action()` 返回结构化 `AgentDecisionOutput`
   - 单个 Agent 决策失败（LLM 超时/解析失败）时自动 fallback 到"观望/不行动"，**不影响其他 Agent**
3. 串行应用行动结果（避免状态竞争）：
   - `AgentEngine.apply_action_result()` **不创建事件节点**
   - 处理 `relation_updates`：每条 update 只操作一条有向边；`source_id` 必须等于当前 Agent，`target_id` 按 ID 优先、名称兜底匹配
   - update 时按 `relation_id` → `(source_id, target_id, relation)` 顺序定位旧边；找不到则降级为 create
   - create 时若同 `(source_id, target_id, relation)` 已存在，则降级为 update
   - 追加 `agent.event_log` 和 `agent.memory`
4. `SimulationEngine._sync_relations_to_topology()` 将全局 `relations` 同步为 `TopologyEdge`
5. `SimulationEngine._update_metrics()` 重新计算指标（合作/冲突占比、网络动荡度、行动多样性、信息熵、活跃指数）
6. `AgentEngine.apply_action_result()` 将 Agent 行动写入 `simulation.timeline`（统一推演日志），含 `action`、`reasoning`、`sentiment_change`、`relation_updates` 及关系变更的 `before/after`
7. `SimulationEngine._generate_round_summary()` 基于本回合 `timeline` 条目自动生成回合摘要（`RoundSummary`），追加到 `simulation.round_summaries`
8. 当前指标快照追加到 `simulation.metrics_history`
9. `SimulationEngine._sync_relations_to_topology()` 将全局 `relations` 同步为 `TopologyEdge`，`_update_metrics()` 重新计算指标
10. 返回推演状态与行动结果

### 前端状态管理

- **Vue 3 新版**使用 Vue 原生 `reactive` + `readonly` 实现极简全局状态（`src/stores/simulationStore.js`），无 Pinia/Vuex 依赖。所有推演数据、UI 状态、干预状态集中管理，API 调用与错误处理内聚在 store 中。
- **React 版**使用 **Zustand**（`src/stores/simulationStore.ts`）管理全局状态。
- `API_BASE = '/api'`（由 Vite 开发服务器代理）；独立 HTML 版则通过 `window.EVENT_SANDBOX_CONFIG` 拼接完整 URL。

## 关键实现细节

- **Repository 模式（文件持久化）** — `FileBasedSimulationRepository` 实现 `SimulationRepository` 抽象接口。每个推演以独立 JSON 文件存储在 `data/simulations/` 目录下，后端启动时自动扫描恢复。内存中仅保留推演摘要（id/name/status/round/agent_count/event_count 等十几个字段），`get()` 时才从磁盘实时加载完整对象（实体、事件、关系、拓扑）。`save()` 时异步写磁盘并更新内存摘要。推演数量增多不会导致内存膨胀，列表查询速度不受影响。
- **异步 LLM 与并发决策** — `AsyncLLMClient` 使用 `httpx.AsyncClient`，一回合内所有 Agent 的 `decide_action()` 通过 `asyncio.gather` 并行发出。单个 Agent LLM 调用失败（超时/解析异常）时自动 fallback 到"观望/不行动"，不影响其他 Agent。
- **LLM JSON 容错** — `AsyncLLMClient._parse_json()` 是关键路径：直接解析 → markdown 代码块提取 → 花括号匹配提取。若修改提示词格式，需确保 JSON 仍能通过三层回退解析。
- **Agent 记忆机制** — `AgentMemory` 维护短期记忆（最多 3 条），溢出时将重要性最高的 3 条归档至长期记忆。仅短期记忆会被送入 LLM 上下文。
- **实体类型扩展与兜底** — `AgentType` 在核心 4 种（company/government/organization/individual）基础上新增 `location`（地点）、`military`（军事单位）、`vehicle`（载具/设备）、`entity`（兜底类型）。LLM 返回未知类型时自动 fallback 到 `entity`，不影响后续流程。类型增减不破坏其他模块。
- **不可行动实体** — `is_actionable=False` 的实体（地点、载具等）保留在图谱和关系中，但 `step()` 时跳过 LLM 决策环节。可行动实体（国家、企业、个人）正常参与推演。`controller_id` 标识不可行动实体的控制者。
- **四步 LLM 图谱构建** — `create_simulation()` 采用分步策略替代一步出图：
  1. **实体提取**（迭代式，最多 3 轮）：先提取明显实体，再检查遗漏，直到 LLM 确认完整或达到上限
  2. **属性构建**（并发）：每个实体并行调用 LLM 生成 `description` + `attributes` + `keywords` + `is_actionable`，受 `ENTITY_BUILD_CONCURRENCY` 限制
  3. **关系提取**：传入所有实体信息，一次性提取关系网络
  4. **图谱组装**：代码层组装 `Topology`、`RelationEdge`、`Simulation`
- **`SimulationEngine.step()` 并发锁** — 每个 simulation 拥有独立的 `asyncio.Lock`，与 FastAPI 异步模型一致，防止同一推演被多个请求并发执行。重复请求会返回 `StepLockedError`。
- **依赖注入** — 全部服务通过 FastAPI `Depends` 注入（`app/dependencies.py`），消灭全局变量。`lifespan` 上下文统一管理 `AsyncLLMClient` 和各服务的生命周期。
- **统一配置** — `core/config.py` 使用 `pydantic-settings` 集中管理所有环境变量，支持 `.env` 文件和环境变量双重来源。
- **并发控制配置** — 实体属性构建通过 `asyncio.Semaphore` 限制并发数，由环境变量 `ENTITY_BUILD_CONCURRENCY` 控制（默认 5）。实体提取迭代轮数由 `ENTITY_EXTRACT_MAX_ROUNDS` 控制（默认 3），短文本可能 1 轮即提前结束，长文本才会触发后续检查。
- **业务异常体系** — `core/exceptions.py` 定义了完整的异常层级。全局异常处理器（`app/main.py`）自动将业务异常转换为标准 HTTP 响应。
- **结构化日志** — 所有模块使用标准 `logging`，格式包含时间戳、级别、模块名。每条关键操作（创建推演、执行 step、Agent 决策、关系更新）均有日志记录。报错信息直接在日志中体现，不会静默吞掉异常。日志同时输出到控制台和 `event_sandbox/backend_v1/logs/backend.log` 文件，方便排查问题。
- **容错设计** — `asyncio.gather(return_exceptions=True)` 保证单个 Agent 决策失败不中断整轮回合；`apply_action_result()` 中每个 `relation_update` 独立 try/catch，避免一个关系更新错误导致后续全部跳过。
- **Agent 模型字段精简** — 已去掉 `deep_profile`（职责由 `description` 承担）、`current_strategy`（始终为空）、`personality_traits` 大五人格（LLM 对自然语言标签理解更好）、`beliefs` 列表（`sentiment` 提升为顶层字段，其余信息 `event_log` 已覆盖）、`resources` 和 `position_x/y`（当前未启用）。
- **干预系统重构** — 干预与回合推进完全分离：
  - `POST /api/simulations/{id}/events` — 事件注入，即刻生效，不推进回合
  - `POST /api/simulations/{id}/step` — 纯回合推进，不再接受干预参数
  - `POST /api/interventions/quick` — 改造为直接调用 `inject_event()`，不再捆绑 `step()`
- **事件注入机制** — `SimulationEngine.inject_event()`：
  1. LLM 自动发现新实体（`extract_entities`）→ 自动创建并补全属性（`build_agent_attributes`）
  2. LLM 全局影响分析（`analyze_external_impact`）→ 支持 ID/名称双匹配的 `_resolve_agent_id()`
  3. 创建 `TopologyNode(node_type="event")` + `TopologyEdge(edge_type="event_affect")`
  4. 更新指标并保存（回合数不变）
- **事件注入 prompt 要求** — `SYS_ANALYZE_EXTERNAL_IMPACT` 强制要求 LLM 为**所有受影响实体**（包括间接影响）返回 `agent_logs`，`source_id`/`target_id` 支持直接使用实体名称
- **Agent 详情编辑** — `AgentDetail` 弹窗支持编辑模式：情绪（数值）、描述（文本域）、性格（文本）、目标（数组增删）、**可行动（复选框）**。`status` 字段已随 `AgentStatus` 枚举一起删除，不再可编辑。点击保存后调用 `POST /api/simulations/{id}/agents/{agent_id}/modify`，修改即时生效。
- **添加实体增强** — `AgentService.add_agent()` 自动调用 `SimulationEngine.build_agent_attributes()` 为新增实体生成 `description`、`personality`、`goals`、`attributes`、`keywords`
- **事件节点策略**：
  - `ACTION` / `REACTION` — ❌ **不创建事件节点**，结果体现在关系边和 `agent.event_log` 中
  - `EXTERNAL` / `INTERVENTION` / `SYSTEM` — ✅ 创建事件节点
- **因果链已删除** — `Event.triggered_by_event_id` 和相关边创建逻辑已移除。
- **Agent 详情响应** — `AgentDetailResponse` 包含 `visible_actions` 字段（从 `simulation.timeline` 筛选该 Agent 可见的 `agent_action` 记录），由 FastAPI 自动序列化返回。
- **前端推演时间轴** — 展示 `simulation.timeline` 中的全部推演日志，包括 Agent 行动（含 `relation_updates`、`reasoning`、`before/after`）、外部事件注入、新增实体。刷新页面后时间轴自动从持久化的 `timeline` 恢复，无需按回合过滤。**支持按 Agent 名称筛选时间轴条目。**
- **推演计数字段** — `Simulation` 模型新增 `agent_count`/`event_count` 字段，`save()` 时自动同步 `len(agents)`/`len(events)`。配合文件持久化的轻量 stub 机制，列表查询无需加载完整实体列表即可返回正确数量。
- **跨域** — `api/main.py` 中 CORS 配置为允许所有来源（`["*"]`）。
- **统一时间轴（timeline）** — `simulation.timeline: list[TimelineEntry]` 替代旧的 `round_actions`，记录所有推演变化：Agent 行动（含 reasoning、relation_updates、before/after）、外部事件注入、新增实体。每回合自动生成 `RoundSummary` 回合摘要，指标历史存入 `metrics_history`。
- **关系语义标注（polarity）** — `RelationEdge` 新增 `id` 字段和 `evolution_history` 字段。每条关系边是有向独立对象，由 `id` 唯一标识；同一对 `(source_id, target_id)` 之间可以有多个不同 `relation` 标签的边。`evolution_history` 记录每次变更后的完整快照，支持历史回放。
- **关系更新定位机制** — Agent 决策时，`relation_updates` 每个元素操作一条有向边，必须包含 `action`（create/update）、`source_id`、`target_id`、`relation`；update 时优先通过 `relation_id` 定位，找不到则按 `(source_id, target_id, relation)` 三元组匹配，再找不到则降级为 create。
- **Agent 只能改 outgoing 关系** — `apply_action_result()` 会校验 `relation_update.source_id` 必须等于当前 Agent，不能修改别人对自己的关系。
- **ID 短 ID 化** — `Agent.id`、`Event.id`、`Simulation.id`、`RelationEdge.id` 均使用 8 位十六进制短 ID，降低 LLM 输出错误率。
- **指标精简** — 移除派生指标 `stability`（稳定性），`innovation`（创新程度）更名为 `action_diversity`（行动多样性），计算逻辑不变。
- **主线推进** — `SimulationConfig` 新增 `main_line: str`，每回合 `step()` 中调用 `generate_main_line_pressure()` 为关键 Agent 生成"主线压力"提示，注入到决策上下文中引导推演方向。
- **新闻向量检索** — `NewsRetriever` 封装 bge-m3 Embedding + Hybase 向量检索，提供 `POST /api/news/search` 接口。干预面板集成"检索相关新闻"按钮，检索结果可一键填入事件描述。
- **初始事件边语义化** — `RelationshipExtractionOutput` 新增 `event_relations`，LLM 在提取关系时同时分析每个实体与初始事件的角色关系（如"发起方"、"遭受打击"），`_build_topology()` 用语义化标签替代硬编码的"影响"。
- **外部事件边语义化** — `SYS_ANALYZE_EXTERNAL_IMPACT` 要求 LLM 在 `agent_logs` 中以 `【影响类型】` 前缀返回影响描述（如"【遭受打击】"），`inject_event()` 解析该前缀作为 `event_affect` 边的 `relation`。
- **JSON 解析增强** — `AsyncLLMClient._parse_json()` 引入 `json_repair.repair_json()` 作为首选修复策略，markdown 代码块和花括号提取作为 fallback，大幅提升 LLM 返回异常 JSON 的解析成功率。
- **报告生成系统** — `ReportEngine` 实现三层报告结构：① 逐 Agent 过程分析（并发 LLM，Top-5 核心 Agent，只描述行动和关系变化，不分析情绪）；② 整体局势描述（单次 LLM，按回合顺序客观描述事实，不总结趋势/脉络/结构）；③ 结论（单次 LLM，必须直接回答推演主线提出的问题，不偏离主线总结过程，不给出泛化建议）。关键点和局势演变脉络已从报告中移除。推演报告和基线报告均持久化到 `Simulation.report` / `Simulation.baseline_report`，支持通过 `GET /api/simulations/{id}/report` 获取，前端 `ReportPanel.vue` 以 Tab 形式展示内容。
- **行动自由生成** — 删除 `ACTION_TEMPLATES` 硬编码模板和 `get_available_actions()` 白名单校验。`SYS_DECIDE_ACTION` 新增【行动自由度】段落，明确告知 LLM "action 可自由生成，不必局限于固定列表"，代码仅在 `action` 为空字符串时兜底到"观望"。同时限制 action 字数在 6 个汉字以内，保证图谱和时间轴展示简洁。
- **决策多样性约束** — `SYS_DECIDE_ACTION` 新增第 5 条原则"避免连续多回合采取相同行动"，`AgentEngine.decide_action()` 提取 Agent 过去 3 回合的 `event_log` 注入 Prompt，让 LLM 明确知道不能重复。
- **Prompt 补充实体与关系列表** — `decide_action()` 的 User Prompt 中新增【所有实体】区块，列出每个实体的 `id`、名称和类型；新增【你当前主动建立的关系】区块，列出每个 outgoing 关系的 `relation_id`、source/target id 和名称、关系标签。帮助 LLM 准确引用 ID 和 relation_id。
- **全局参数精简** — 删除 `Simulation` 模型中的 `global_sentiment` 和 `market_conditions` 冗余字段。`global_params` 不再作为独立参数传给 LLM，Agent 看到的全局上下文完全由实时 `metrics` 和动态 `environment_state` 驱动。
- **干预服务清理** — 删除 `InterventionService.quick_intervene()` 死代码（路由层已直接调用 `engine.inject_event()`）。`InterventionType.GLOBAL_PARAM` 保留枚举值但不再处理。
- **短期记忆容量收紧** — `AgentMemory.max_short_term` 从 20 改为 3，LLM 上下文更精炼，只保留最近 3 条记忆。
- **推演时间切片** — 创建推演时可配置起始时间和每回合代表的真实时长。详见下方「推演时间切片」独立小节。
- **事件日志展示增强** — `AgentDetail.vue` 中"事件日志"从单行（回合+动作名）改为多行卡片，展示 `content`（做了什么）和 `reasoning`（为什么这么做），并增加独立样式区分。外部干预注入时，agent 的 `event_log` 中 `type` 字段值为 `"外部干预"`（原 `"external"`），便于前端区分展示。
- **指标改名与悬停增强** — "主动权指数"更名为"活跃指数"（`initiative_index`）。`MetricsDashboard.vue` 悬停时展示完整 sparkline：Y 轴数值标注（每个点都有）、X 轴回合标注（R1~R5）、水平参考线、tooltip 宽度自适应。
- **推演时间轴回合标注** — `ActionTimeline.vue` 每个条目头部新增 `R{round}` 黑底白字回合徽章，与 action-type 标签并排显示。
- **基线报告系统（BaselineReportEngine）** — 新增纯 LLM 线性推演报告引擎，与基于图谱的 `ReportEngine` 解耦。输入为推演背景 + 初始事件描述 + 推演主线 + 已推进回合数 + 涉及实体列表，输出同构报告结构（agent_summaries / overall_summary / conclusion / full_report），持久化到 `Simulation.baseline_report`。结论同样要求直接回答推演主线提出的问题。用于与图谱推演报告进行对比验证。基线报告不包含推演过程中的 timeline、relations、干预记录等动态信息。
- **报告对比视图** — `ReportPanel.vue` 新增视图模式切换栏（推演报告 / 基线报告 / 对比）。两份报告都存在时默认展示单栏，用户手动点击"对比"才进入左右分栏。默认视图由 `lastAction` prop 控制：生成推演报告 → 默认推演单栏；生成基线报告 → 默认基线单栏；同时生成两者 → 默认对比分栏。
- **报告生成逻辑** — `SimulationView.vue` 中 `refreshSimulation()` 加载推演状态后**不再自动调用 `store.getReport()`**，避免切换推演时旧报告残留；用户点击顶部"报告"按钮打开面板时，若当前没有报告则**自动尝试加载已保存报告**；面板内空状态提供"生成推演报告 / 生成基线报告 / 同时生成两者"三个按钮。`ReportPanel` 单栏视图下"重新生成"按钮会根据当前视图模式（推演/基线）生成对应报告，避免在基线报告界面误生成图谱报告。
- **Markdown 渲染完整报告** — `ReportPanel.vue` 引入 `marked` 库渲染完整报告 Tab，支持标题、列表、引用、代码块、粗体等 Markdown 语法，替代原有的 `<pre>` 纯文本展示。

## 推演时间切片

为让 Agent 决策具备真实时间感，系统支持为每个推演配置**起始时间**和**每回合代表时长**。时间配置在创建时确定，创建后不可修改。

### 配置字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `start_datetime` | `datetime` | 推演起始模拟时间（默认当前时间） |
| `round_duration_value` | `float` | 每回合时长数值（≥0.1） |
| `round_duration_unit` | `str` | 时间单位：`round`（无时间语义）、`minute`、`hour`、`day`、`week`、`month`、`quarter`、`year` |

当 `round_duration_unit` 为 `round` 时，系统认为该推演没有时间语义，`has_time_semantics` 返回 `False`，Agent 决策 prompt 中不注入时间上下文。

### 时间推进规则

- 创建推演时，`Simulation.model_post_init()` 自动根据 `current_round=0` 计算 `current_simulated_time`。
- 每执行一次 `SimulationEngine.step()`，`current_round += 1`，随后调用 `Simulation.update_simulated_time()` 重新计算当前模拟时间。
- 时间换算基于 `TIME_UNIT_DAYS` 映射：`month` 按 30 天、`quarter` 按 90 天、`year` 按 365 天近似处理。

### Agent 决策上下文

`Simulation.get_time_context()` 返回以下字段，供 `AgentEngine.decide_action()` 注入 LLM prompt：

- `current_round`：当前回合
- `total_rounds`：总回合数
- `current_simulated_time`：格式化的当前模拟时间
- `start_datetime`：格式化的起始时间
- `round_duration`：可读的单位描述（如 "1天"）
- `has_time_semantics`：是否启用时间语义

### 前端交互

- 创建页面（`Home.vue`）提供 `datetime-local` 起始时间输入和「每回合时长」数值+单位选择。
- 推演控制台顶部（`SimulationView.vue`）显示格式化后的当前模拟时间，例如 `2026-06-10 09:00`。

### 使用示例

- **足球比赛推演**：90 分钟分 10 回合，每回合 9 分钟。
- **地缘政治推演**：每回合代表 1 天，便于按自然日理解各方反应节奏。
- **商业竞争推演**：每回合代表 1 周或 1 季度，聚焦中长期战略演变。

## 场景感知推演架构（方案 C）

系统在关系驱动内核之上，引入了**场景世界模型（Scenario World Model）**，使 `world_state` 和离散事件成为与 `relations` 并列的一等公民。该架构采用**混合方案**：代码负责状态执行与终止判断，LLM 负责场景理解与行动生成。

### 核心对象

- **`ScenarioWorldModel`**（`core/domain/world_model.py`）：场景世界模型，创建推演时由 LLM 根据初始事件自动生成。
  - `scenario_type`：场景类型（如 `football_match`、`geopolitics`、`business`）。
  - `world_state_schema`：需要跟踪的世界状态字段及类型。
  - `event_types`：离散事件类型列表，仅用于分类，不是动作白名单。
  - `terminal_condition`：终止条件表达式（如 `match_phase == 'full_time'`）。
  - `action_grammar`：行动如何改变世界状态的说明。
  - `initial_world_state`：初始世界状态。
  - `outcome_evaluation`：如何回答推演主线问题。
- **`WorldEvent`**：离散事件，记录 `type`、`round`、`actor`、`description`、`metadata`。
- **`Simulation`** 扩展字段：
  - `world_model: ScenarioWorldModel | None`
  - `world_state: dict`
  - `world_state_history: list[dict]`
  - `world_events_history: list[WorldEvent]`

### 推演流程

1. **世界模型构建**：创建推演时，在实体和关系提取之后，调用 `extract_world_model()` 生成场景世界模型，初始化 `world_state` 并记录初始快照。
2. **Agent 决策**：`decide_action()` Prompt 中注入当前世界状态说明和事件类型。Agent 输出 `action + world_state_updates + events + relation_updates`。
3. **状态与事件应用**：
   - `update_world_state(updates)` 按 schema 类型安全地更新状态（数字类型自动转换）。
   - `add_world_event(event)` 将离散事件追加到 `world_events_history`。
   - 事件同时生成 `world_event` 类型的 `TimelineEntry`。
4. **终止判断**：每回合结束后调用 `check_terminal_condition()`，使用 AST 白名单安全求值 `terminal_condition`。默认在 `current_round >= rounds` 时结束。
5. **报告生成**：`ReportEngine` 基于 `world_state_history` 和 `world_events_history` 生成事实时间线，结论必须基于最终 `world_state` 回答推演主线问题。

### 终止条件表达式

`Simulation._eval_safe_expression()` 支持以下运算符和结构：

- 比较：`==`、`!=`、`<`、`<=`、`>`、`>=`
- 布尔：`and`、`or`、`not`
- 成员：`in`
- 算术：`+`、`-`
- 容器：列表、元组

不支持函数调用、属性访问、赋值等。表达式解析失败时按回合数兜底，不阻断推演。

### 前端展示

- `SimulationView.vue` 顶部展示关键世界状态（如比分、比赛阶段、球权）。
- `ActionTimeline.vue` 展示 `world_event` 类型条目，并渲染事件元数据标签。

## 知识图谱约束系统

`KnowledgeGraph`（`core/knowledge/graph.py`）当前处于**开放模式**：

- `validate_action()` 始终返回 True，不再进行语义校验
- 关系类型为完全自由字符串，由 LLM 根据语义动态生成
- `get_knowledge_context()` 从全局 `relations` 构建上下文，供 Agent 决策参考

## 拓扑与可视化

拓扑结构（`Topology` / `TopologyNode` / `TopologyEdge`）驱动前端 D3 图谱渲染：

- **节点类型**（`node_type`）：`agent` / `event` / `env` / `place` / `concept`。当前仅创建 `agent` 和 `event` 节点。
- **边类型**（`edge_type`）：`agent_relation`（Agent 间关系）、`event_affect`（事件影响）、`env_influence`（环境干预）、`place_link`（地点关联）。**`caused_by`（因果链）已删除。**
- **有向边语义**：`TopologyEdge` 为 DiGraph 有向边。`SYMMETRIC_RELATIONS` 概念保留但不再强制约束双向一致性；A→B 和 B→A 可以各自有不同的 `relation` 和 `description`。
- **事件影响边**：`inject_event()` 注入外部事件时，创建 `event_affect` 边连接事件节点与所有受影响 Agent（来源：`impact.agent_logs` 和 `impact.relation_updates` 中涉及的实体）。初始事件也在 `_build_initial_topology()` 中创建 `event_affect` 边。
- **拓扑同步** — `_sync_relations_to_topology()` 将 `simulation.relations` 同步为 `TopologyEdge`。当前采用**清空重建**策略：先移除 topology 中所有 `agent_relation` 边，再根据当前 `relations` 重新创建，避免旧数据格式冲突。
- **前端图谱过滤与回放** — `GraphPanel.vue` 支持"全部关系/只看本回合/最近 N 回合"过滤，以及按创建回合回放（过滤显示创建回合 ≤ 回放回合的边）。边详情面板展示关系描述、交互次数、最近更新回合和 `evolution_history` 演变历史。

## 推演指标详解

所有指标在 `_update_metrics()` 中每回合自动重新计算。

### 全局指标（SimulationMetrics）

| 指标 | 范围 | 含义 | 计算方式 |
|------|------|------|----------|
| `network_turbulence` | 0 ~ 1 | **网络动荡度** | 本回合发生变更的关系边数 ÷ 总关系边数 |
| `cooperation_level` | 0 ~ 1 | **合作水平** | `polarity == "positive"` 的关系边数 ÷ 总关系边数 |
| `conflict_level` | 0 ~ 1 | **冲突程度** | `polarity == "negative"` 的关系边数 ÷ 总关系边数 |
| `action_diversity` | 0 ~ 1 | **行动多样性** | `本回合不同行动种类数 / Agent 总数 × 0.5` |
| `information_entropy` | 0 ~ 1 | **信息熵** | 基于本回合行动的 Shannon 熵。0=局势单一，1=多方混战 |
| `initiative_index` | 0 ~ 1 | **活跃指数** | 本回合采取非"观望"行动的 Agent 比例，反映推演活跃度 |

### Agent 个体指标

| 指标 | 范围 | 含义 |
|------|------|------|
| `sentiment` | -1 ~ 1 | **当前情绪值**，通过行动和干预实时变化 |
| `emotional_intensity` | 0 ~ 1 | **情绪激烈程度**，每次行动后增加 `abs(情绪变化) × 0.2` |
| `action_count` | 0+ | **累计行动次数** |

### 保留字段（尚未启用动态计算）

- `TopologyEdge.weight` — 固定 0.5，可用于未来表示关系强度
- `SimulationMetrics.custom_metrics` — 预留扩展字段

## 测试与质量

backend_v1 已建立基础测试套件，位于 `backend_v1/tests/`：

- **`tests/test_domain.py`** — 领域模型单元测试（Agent、Simulation、Memory、Relation 等纯数据结构的校验与行为测试）
- **`tests/test_engine.py`** — 引擎层集成测试（创建推演、执行 step、异常场景）
- **`conftest.py`** — pytest fixture 定义（`repo`、`llm_client`、`engine`、`sim_service` 等共享依赖）

运行测试：
```bash
cd event_sandbox/backend_v1
python -m pytest tests/ -v
```

`pyproject.toml` 已将 `pytest`、`pytest-asyncio`、`black`、`ruff`、`pydantic-settings` 列为可选开发依赖。

## 代码风格提示

- 后端使用 Pydantic v2（`BaseModel`、`Field`、`model_dump()`）。
- `backend_v1` 为包结构，所有模块通过相对/绝对导入工作，**不再使用 `sys.path` 注入**。
- 独立 HTML 前端已分离为 `index.html` + `config.js` + `style.css` + `app.js` 四个文件。React 组件复现了相同的功能结构，类型定义与后端严格对齐（snake_case）。
- `backend_v1` 日志使用标准 `logging` 模块，所有关键操作必须记录日志，异常必须 `exc_info=True` 记录完整堆栈。

## 相关文档

- **`event_sandbox/backend_v1/docs/core-mechanism-redesign.md`** — 记录关于推演核心机制改造的讨论，包括当前「单轮单次 LLM 输出 action + relation_updates」模式的本质问题，以及未来可能的改造方向（策略-行动双层决策、信念-期望-行动循环 / BDI 模型、博弈论显式推理、反事实分支等）。该文档用于保留设计讨论，当前代码尚未实现其中方案。
- **`event_sandbox/backend_v1/docs/scenario-aware-architecture.md`** — 场景感知推演架构文档。当前已实现方案 C（混合方案）：代码负责状态执行与终止判断，LLM 负责场景理解与行动生成。

## 全局工作约定

1. **语言要求**：回答用户问题和代码中的注释必须使用中文。
2. **Python 环境**：使用 Python 时，必须调用 `C:\Users\TRS\miniconda3\envs\py310\python`（Conda py310 环境），而不是系统默认的 `python`。例如：
   ```bash
   C:\Users\TRS\miniconda3\envs\py310\python -m uvicorn api.main:app --reload
   ```
