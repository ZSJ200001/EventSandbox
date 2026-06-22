# EventSandbox - 可干预的智能事件推演沙盘

## 项目概述

EventSandbox 是一款基于多智能体（Multi-Agent）架构的 AI 原生决策支持系统。系统突破传统预测工具"单次输出、不可干预"的局限，构建了一个可实时操控的数字孪生推演环境，让用户能够像指挥沙盘演习一样，低成本、可视化地预演各类事件的演化路径。

**核心设计理念**：关系驱动推演 —— Agent 的每次行动不再堆积为孤立的事件节点，而是实时更新 Agent 之间的语义关系，让图谱的演化真正反映行动的影响。

## 核心功能

### 1. 智能输入解析
- 自动提取关键主体（人、组织、概念）
- 识别相互关系，构建事件拓扑
- 基于结构动态生成具备独立人格与目标的智能体

### 2. 多Agent自主推演（关系驱动）
- 各 Agent 基于大语言模型自主决策
- 每回合 LLM 输出关系语义更新，代码实时写入图谱
- **Agent 行动不创建事件节点**，结果体现在关系边变化和 Agent 行动日志中
- 支持双向语义独立（如 美国→伊朗="军事打击"，伊朗→美国="遭受打击"）

### 3. 实时干预操控（三层干预）
- **全局参数调整**: 修改市场情绪指数等全局环境参数
- **Agent状态修改**: 注入新信息、改变Agent情绪或信念
- **强制触发外部事件**: 如监管介入、突发新闻等
- 外部事件/干预触发全局 LLM 分析，先更新关系再让 Agent 决策

### 4. 可视化决策洞察
- Agent 关系网络实时变化（带自然语言描述的关系边）
- 关键事件时间轴（仅展示外部/干预/系统事件）
- Agent 行动日志面板
- 多维度指标仪表盘
- 干预前后对比分析报告

## 技术架构

```
event_sandbox/
├── backend_v1/                # Python FastAPI 后端（推荐）
│   ├── app/                  # FastAPI 应用层（路由、依赖注入、全局异常）
│   ├── core/                 # 业务核心（配置、异常、领域模型）
│   ├── engines/              # 推演引擎（SimulationEngine、AgentEngine、BaselineReportEngine）
│   ├── services/             # 业务服务层
│   ├── infrastructure/       # 基础设施（LLM Client、持久化、事件总线）
│   ├── schemas/              # API 输入输出 Pydantic 模型
│   └── tests/                # 测试套件
├── frontend_v1/               # Vue 3 前端（推荐）
│   ├── src/                  # Vue 3 Composition API 源码
│   └── index.html            # Vite 入口
└── docs/                      # 项目文档
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（前端开发，可选）
- LLM API 访问权限

### 1. 启动后端服务

```bash
cd event_sandbox/backend_v1

# 安装依赖
pip install fastapi uvicorn pydantic httpx networkx pydantic-settings

# 启动服务器
C:\Users\TRS\miniconda3\envs\py310\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

或使用启动脚本：
```bash
# Windows PowerShell
.\start.ps1

# Linux/Mac
chmod +x start.sh
./start.sh
```

### 2. 访问前端

```bash
cd event_sandbox/frontend_v1
npm install
npm run dev      # 端口 3000，自动代理 /api 到 localhost:8000
```

## API接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/simulations` | POST | 创建新推演 |
| `/api/simulations` | GET | 列出推演 |
| `/api/simulations/{id}` | GET | 获取推演状态 |
| `/api/simulations/{id}/step` | POST | 执行一回合推演 |
| `/api/simulations/{id}/batch-step` | POST | 批量执行多回合 |
| `/api/simulations/{id}/events` | POST | 注入外部事件（不推进回合） |
| `/api/simulations/{id}/agents` | POST | 动态添加 Agent |
| `/api/simulations/{id}/agents/{id}/modify` | POST | 修改 Agent 属性 |
| `/api/simulations/{id}/pause` | POST | 暂停推演 |
| `/api/simulations/{id}/resume` | POST | 恢复推演 |
| `/api/simulations/{id}/report` | POST | 生成推演报告 |
| `/api/simulations/{id}/report/baseline` | POST | 生成基线报告 |
| `/api/interventions/options` | GET | 获取干预选项 |

完整API文档: `http://localhost:8000/docs`

## 配置说明

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `LLM_API_BASE` | http://101.251.216.47/8411/v1 | LLM API地址 |
| `LLM_API_KEY` | sk-empty | API密钥 |
| `DEFAULT_MODEL` | Qwen3-Coder-Next | 默认模型 |
| `PORT` | 8000 | 服务端口 |

## 使用示例

```python
import requests

# 1. 创建推演
sim = requests.post("http://localhost:8000/api/simulations", json={
    "name": "美伊冲突推演",
    "description": "美伊冲突推演场景",
    "event_text": "美国对伊朗核设施发动精确打击"
}).json()

sim_id = sim['simulation']['id']

# 2. 执行一回合
requests.post(f"http://localhost:8000/api/simulations/{sim_id}/step")

# 3. 注入外部事件（不推进回合）
requests.post(f"http://localhost:8000/api/simulations/{sim_id}/events", json={
    "description": "联合国安理会呼吁双方停火"
})

# 4. 动态添加 Agent
requests.post(f"http://localhost:8000/api/simulations/{sim_id}/agents", json={
    "name": "国际社会",
    "type": "organization"
})

# 5. 生成推演报告
requests.post(f"http://localhost:8000/api/simulations/{sim_id}/report", json={})

# 6. 生成基线报告
requests.post(f"http://localhost:8000/api/simulations/{sim_id}/report/baseline")
```

## 应用场景

- **企业战略**：新产品发布、价格调整、并购决策的后果预估
- **公共政策**：政策出台后的社会反应、舆论演化推演
- **风险管理**：突发事件的多米诺效应预演
- **国际关系**：军事冲突、外交博弈的多方推演
- **创意写作**：角色在不同事件后的剧情分支推演

## 项目状态

✅ 核心功能开发完成
✅ 关系驱动推演架构重构完成
✅ 后端API服务正常运行
✅ LLM集成连接成功
✅ 前端 Vue 3 界面正常运行

---

