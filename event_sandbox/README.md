# EventSandbox - 可干预的智能事件推演沙盘

EventSandbox 是一款基于多智能体（Multi-Agent）架构的 AI 原生决策支持系统。系统突破传统预测工具"单次输出、不可干预"的局限，构建了一个可实时操控的数字孪生推演环境，让用户能够像指挥沙盘演习一样，低成本、可视化地预演各类事件的演化路径。

## 核心特性

### 1. 智能输入解析
用户输入任意事件描述（新闻、政策、商业决策等），系统自动提取关键主体（人、组织、概念），识别相互关系，构建事件拓扑，并基于结构动态生成具备独立人格与目标的智能体（Agent）。

### 2. 多Agent自主推演
各 Agent 基于大语言模型自主决策，通过感知环境、推理判断、执行行动的回合制循环，模拟真实世界中的多方博弈与连锁反应，产生具备涌现性的演化结果。

### 3. 实时干预操控
用户可在推演任意节点进行三层干预：
- **全局参数调整**：修改市场情绪指数等全局环境参数
- **Agent状态修改**：注入新信息、改变Agent情绪或信念
- **强制触发外部事件**：如监管介入、突发新闻等

### 4. 可视化决策洞察
系统提供沙盘级可视化界面：
- Agent 关系网络实时变化
- 关键事件时间轴
- 多维度指标仪表盘
- 干预前后对比分析报告

## 技术架构

```
event_sandbox/
├── backend/
│   ├── api/            # FastAPI REST API
│   ├── core/           # 核心引擎
│   │   ├── agent/      # Agent决策引擎
│   │   ├── event_parser/   # 事件解析模块
│   │   ├── knowledge/   # 知识图谱
│   │   ├── llm/        # LLM集成层
│   │   └── simulation/ # 仿真引擎
│   ├── models/         # Pydantic数据模型
│   └── services/       # 业务服务层
├── frontend/           # React + TypeScript前端
│   └── src/
│       ├── components/  # UI组件
│       ├── stores/     # Zustand状态管理
│       ├── types/      # TypeScript类型定义
│       └── utils/      # 工具函数
└── docs/               # 项目文档
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+ (前端开发)
- LLM API访问权限

### 后端启动

```bash
cd event_sandbox/backend

# 安装依赖
pip install fastapi uvicorn pydantic httpx networkx

# 启动服务器
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

或使用启动脚本：
```bash
# Windows
.\start.ps1

# Linux/Mac
chmod +x start.sh
./start.sh
```

### 前端启动

```bash
cd event_sandbox/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### Docker部署

```bash
# 构建镜像
docker build -t eventsandbox:latest .

# 运行容器
docker run -p 8000:8000 eventsandbox:latest
```

## API文档

启动后端服务后，访问 `http://localhost:8000/docs` 查看完整的API文档。

### 主要接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/simulations` | POST | 创建新推演 |
| `/api/simulations` | GET | 列出推演 |
| `/api/simulations/{id}` | GET | 获取推演状态 |
| `/api/simulations/{id}/step` | POST | 执行一步推演 |
| `/api/simulations/{id}/batch-step` | POST | 批量执行多步 |
| `/api/simulations/{id}/intervene` | POST | 注入干预 |
| `/api/simulations/{id}/compare` | POST | 场景对比分析（推荐） |
| `/api/simulations/{id}/compare` | GET | 场景对比分析（旧版兼容） |
| `/api/simulations/{id}/pause` | POST | 暂停推演 |
| `/api/simulations/{id}/resume` | POST | 恢复推演 |

## 使用示例

### 1. 创建推演场景

```python
import requests

response = requests.post("http://localhost:8000/api/simulations", json={
    "name": "奶茶涨价推演",
    "description": "模拟奶茶品牌涨价后的市场反应",
    "event_text": "XX奶茶招牌产品涨价3元"
})
simulation = response.json()
```

### 2. 执行推演

```python
# 推进一回合
response = requests.post(
    f"http://localhost:8000/api/simulations/{simulation['id']}/step",
    json={"simulation_id": simulation['id']}
)

# 带干预推进
response = requests.post(
    f"http://localhost:8000/api/simulations/{simulation['id']}/step",
    json={
        "simulation_id": simulation['id'],
        "intervention": {
            "id": "int1",
            "type": "external_event",
            "value": "监管部门约谈奶茶品牌",
            "timestamp": 0,
            "round": 0
        }
    }
)
```

### 3. 场景对比

```python
response = requests.get(
    f"http://localhost:8000/api/simulations/{simulation['id']}/compare",
    params={
        "intervention_type": "agent_state",
        "target": agent_id,
        "parameter": "sentiment",
        "value": "0.8"
    }
)
report = response.json()
```

## 配置说明

### 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `LLM_API_BASE` | http://101.251.216.47/8411/v1 | LLM API地址 |
| `LLM_API_KEY` | sk-empty | API密钥 |
| `DEFAULT_MODEL` | Qwen3-Coder-Next | 默认模型 |
| `PORT` | 8000 | 服务端口 |

## 应用场景

- **企业战略**：新产品发布、价格调整、并购决策的后果预估
- **公共政策**：政策出台后的社会反应、舆论演化推演
- **风险管理**：突发事件的多米诺效应预演
- **创意写作**：角色在不同事件后的剧情分支推演

## 开发团队

- 参赛赛道：赛道A（商业创新线）
- 参赛人：昝世杰
- 部门：北京研发中心-认知计算组

## 许可证

MIT License
