# EventSandbox - 可干预的智能事件推演沙盘

## 项目概述

EventSandbox 是一款基于多智能体（Multi-Agent）架构的 AI 原生决策支持系统。系统突破传统预测工具"单次输出、不可干预"的局限，构建了一个可实时操控的数字孪生推演环境，让用户能够像指挥沙盘演习一样，低成本、可视化地预演各类事件的演化路径。

**参赛赛道**: 赛道A（商业创新线）
**参赛人**: 昝世杰
**部门**: 北京研发中心-认知计算组

## 核心功能

### 1. 智能输入解析
- 自动提取关键主体（人、组织、概念）
- 识别相互关系，构建事件拓扑
- 基于结构动态生成具备独立人格与目标的智能体

### 2. 多Agent自主推演
- 各 Agent 基于大语言模型自主决策
- 感知环境、推理判断、执行行动的回合制循环
- 模拟多方博弈与连锁反应

### 3. 实时干预操控（三层干预）
- **全局参数调整**: 修改市场情绪指数等全局环境参数
- **Agent状态修改**: 注入新信息、改变Agent情绪或信念
- **强制触发外部事件**: 如监管介入、突发新闻等

### 4. 可视化决策洞察
- Agent 关系网络实时变化
- 关键事件时间轴
- 多维度指标仪表盘
- 干预前后对比分析报告

## 技术架构

```
event_sandbox/
├── backend/                    # Python FastAPI 后端
│   ├── api/                  # REST API 接口
│   ├── core/                 # 核心引擎
│   │   ├── agent/           # Agent决策引擎
│   │   ├── event_parser/    # 事件解析模块
│   │   ├── knowledge/       # 知识图谱
│   │   ├── llm/            # LLM集成层
│   │   └── simulation/      # 仿真引擎
│   ├── models/              # Pydantic数据模型
│   └── services/            # 业务服务层
├── frontend/                  # 前端
│   ├── index.html           # 可独立运行的HTML版本
│   └── src/                 # React源码
└── docs/                     # 项目文档
```

## 快速开始

### 1. 启动后端服务

```bash
cd event_sandbox/backend

# 安装依赖
pip install fastapi uvicorn pydantic httpx networkx

# 启动服务器
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 访问前端

打开 `event_sandbox/frontend/index.html` 即可使用（无需构建）

或启动开发服务器（如已安装Node.js）:
```bash
cd event_sandbox/frontend
npm install
npm run dev
```

### 3. Docker部署

```bash
cd event_sandbox
docker-compose up -d
```

## API接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/simulations` | POST | 创建新推演 |
| `/api/simulations/{id}` | GET | 获取推演状态 |
| `/api/simulations/{id}/step` | POST | 执行一步推演 |
| `/api/simulations/{id}/intervene` | POST | 注入干预 |
| `/api/simulations/{id}/compare` | GET | 场景对比分析 |

完整API文档: `http://localhost:8000/docs`

## 配置说明

环境变量:
- `LLM_API_BASE`: LLM API地址（默认: http://101.251.216.47/8411/v1）
- `LLM_API_KEY`: API密钥
- `DEFAULT_MODEL`: 默认模型（默认: Qwen3-Coder-Next）

## Demo场景

奶茶品牌涨价事件推演:
1. 输入: "XX奶茶招牌产品涨价3元"
2. 系统自动识别: 品牌方、消费者、竞品、供应商、监管部门
3. 推演: 各Agent自主决策，观察连锁反应
4. 干预: 注入"监管部门约谈"事件
5. 分析: 生成对比报告

## 项目状态

✅ 核心功能开发完成
✅ 后端API服务正常运行
✅ LLM集成连接成功
✅ 前端界面可独立运行
✅ Docker配置完成

---

**日期**: 2026年3月29日
