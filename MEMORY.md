# EventSandbox 项目公共记忆

## 项目概述

**项目名称**: EventSandbox - 可干预的智能事件推演沙盘
**参赛赛道**: 赛道A（商业创新线）
**参赛人**: 昝世杰
**部门**: 北京研发中心-认知计算组
**项目路径**: `D:\code\EventSandbox`

### 核心功能

1. **智能输入解析** - 输入事件文本，自动提取主体并生成Agent网络
2. **多Agent自主推演** - 基于LLM的Agent决策循环
3. **三层实时干预** - 注入外部事件、影响Agent、全局环境
4. **可视化决策洞察** - 网络图谱、时间轴、指标仪表盘、对比报告

---

## 技术架构

```
event_sandbox/
├── backend/
│   ├── api/main.py           # FastAPI REST API
│   ├── core/
│   │   ├── agent/engine.py   # Agent决策引擎
│   │   ├── event_parser/     # 事件解析与Agent生成
│   │   ├── knowledge/graph.py # 知识图谱约束
│   │   ├── llm.py           # LLM集成层
│   │   └── simulation/engine.py # 仿真引擎
│   └── models/               # Pydantic数据模型
├── frontend/
│   ├── index.html            # 可独立运行的完整前端（已重构）
│   ├── config.js             # 前端配置文件
│   └── src/                  # React源码（未完成）
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### LLM配置
- **API地址**: http://101.251.216.47/8411/v1
- **默认模型**: Qwen3-Coder-Next

---

## 用户明确要求（重要）

### 1. 配置统一放置
- **要求**: 所有配置参数必须统一放在一个文件中，不要散落在各处
- **当前状态**: `frontend/config.js` 包含前端配置

### 2. 后端端口可配置
- **要求**: 后端端口不要写死，前端能通过配置文件指定
- **当前状态**: 前端默认连接 `localhost:8010`，后端可能运行在不同端口

### 3. 界面不需要全屏转圈
- **要求**: 操作响应应该局部加载，不要全屏遮罩
- **改进**: 使用内联Loading + 右下角Toast通知

### 4. Agent状态可查看
- **要求**: 用户能查看各个Agent的详细信息
- **改进**: 点击Agent卡片弹出详情弹窗

### 5. 网络图可缩放拖拽
- **要求**: 知识图谱网络需要支持缩放、平移、拖拽节点
- **改进**: 已添加滚轮缩放、右上角缩放按钮、节点可拖拽

---

## 修改记录

### 2026-04-25

1. **前端配置统一**
   - 创建 `frontend/config.js` 存放所有配置
   - API_HOST, API_PORT, API_BASE_PATH 集中管理

2. **干预功能重构**
   - 原问题: "全局参数"和"Agent状态"都是数值调节，不直观
   - 改进: 三种干预类型
     - 注入事件（快速按钮 + 自定义）
     - 影响Agent（选择Agent + 快速影响方式）
     - 全局环境（快速选择环境变化）

3. **界面体验改进**
   - 去除全屏loading遮罩
   - 使用内联spinner + Toast通知
   - 添加Agent详情弹窗
   - 网络图添加缩放/拖拽功能

4. **Health端点修复**
   - 原问题: health在 `/health` 不是 `/api/health`
   - 修复: 前端分别使用 `API_HOST_URL` 和 `API_BASE`

5. **HTML结构修复**
   - 原问题: render()操作不存在的DOM元素导致空白页
   - 修复: 预定义HTML结构模板

---

## 已知问题

1. **前端直接打开file://无法工作**: 必须通过HTTP服务器访问
2. **React源码未完成**: `frontend/src/` 下的是占位文件，实际使用 `index.html` 单文件版本

---

## 启动方式

### 后端
```bash
cd D:\code\EventSandbox\event_sandbox\backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8010
```

### 前端（方式1 - Python服务器）
```bash
cd D:\code\EventSandbox\event_sandbox\frontend
python -m http.server 3000
# 访问 http://localhost:3000
```

### 前端（方式2 - 直接打开）
直接打开 `index.html` 但必须先启动后端，且通过3000端口访问

---

## 后端API端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查（注意：不在/api下）|
| `/api/simulations` | POST | 创建推演 |
| `/api/simulations/{id}` | GET | 获取推演状态 |
| `/api/simulations/{id}/step` | POST | 执行推进一步 |
| `/api/simulations/{id}/intervene` | POST | 注入干预 |
| `/api/simulations/{id}/compare` | GET | 场景对比 |

---

## 用户习惯与偏好

- 喜欢快速反馈，不喜欢等待全屏loading
- 希望所有配置集中管理
- 注重界面交互体验（拖拽、缩放）
- 使用Windows系统
- 使用中文交流

---

*最后更新: 2026-04-25*
