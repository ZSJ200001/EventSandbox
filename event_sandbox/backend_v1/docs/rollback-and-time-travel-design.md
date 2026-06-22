# 推演系统「随时回溯」功能设计讨论

> 记录日期：2026-06-22
> 讨论主题：后端是否需要支持任意回合回溯、当前文件持久化是否合适、是否引入图数据库

## 1. 背景与问题

当前系统已实现基于多 Agent 的回合制事件推演，支持：

- 创建推演并自动提取实体、关系、场景世界模型
- 每回合并行驱动可行动 Agent 决策
- 外部事件注入（不推进回合）
- 推演报告与基线报告生成

但系统目前只保存推演的**最新状态**，没有保留历史回合的完整状态。如果用户希望"随时回溯到第 N 回合重新推演"，当前架构无法直接支持。

## 2. 当前持久化方式评估

当前采用 `FileBasedSimulationRepository`，每个推演保存为：

```
data/simulations/{id}.json
```

### 2.1 优势

- 实现简单，无需外部依赖
- 单文件可移植，便于备份和查看
- 重启时自动扫描恢复
- 单个推演 JSON 通常几百 KB 到几 MB，I/O 压力可控

### 2.2 局限

- 每次 `save()` 全量覆盖写入，只保留最终状态
- 无法直接回溯到历史回合
- 随着推演进行，文件持续增长，但仍在可接受范围

**结论**：当前文件存储方式作为"主存储"仍然合适，问题在于"缺少历史状态记录机制"，而非存储介质本身。

## 3. 回溯功能的两种实现路径

### 方案 A：每回合完整 Snapshot（推荐首选）

每执行一次 `step()` 或 `inject_event()` 前后，保存当前 `Simulation` 完整对象的副本。

```
data/simulations/{id}.json              # 当前最新状态
data/snapshots/{id}/R1.json
data/snapshots/{id}/R2.json
data/snapshots/{id}/R3.json
```

回溯时直接加载 `R5.json` 替换内存中的 `Simulation`。

#### 优点

- 实现简单，回溯速度快
- 不改动现有领域模型和推演逻辑
- 代码改动集中在 `SimulationEngine` 和 Repository 层
- 磁盘占用可接受：1000 回合 × 500KB ≈ 500MB

#### 缺点

- 存储空间随回合线性增长
- 不支持从同一回合分叉出多条推演路径（分支推演）

### 方案 B：Event Sourcing（事件溯源）

只保存：

1. 初始推演状态（创建时的完整对象）
2. 每一回合的事件记录（Agent 决策结果、relation_updates、world_state_updates、干预记录等）

回溯时从初始状态重放事件到目标回合。

#### 优点

- 存储体积小
- 天然支持审计："某一时刻为什么变成这样"
- 支持分支推演和反事实分析

#### 缺点

- 实现复杂，重放必须幂等且稳定
- LLM 输出不可复现，必须把每回合 LLM 返回的决策结果作为事件持久化
- 对现有代码改动较大

## 4. 是否需要引入图数据库

**结论：目前不推荐引入图数据库。**

| 图数据库优势 | 当前系统是否需要 |
|------------|---------------|
| 快速遍历多层关系（A→B→C→D） | 否。Agent 决策主要依赖局部关系上下文 |
| 大规模关系网络查询 | 否。单个推演关系边通常 < 1000，内存+JSON 足够 |
| 版本化图与历史状态查询 | 否。这是 snapshot/event sourcing 解决的问题 |

如果未来出现以下需求，再考虑 Neo4j / Dgraph / ArangoDB：

- 跨推演的关系分析与模式挖掘
- 实时大规模图谱可视化
- 需要复杂图算法（社区发现、中心性分析等）

## 5. 推荐的最小可行方案

优先采用**方案 A（Snapshot）+ 文件存储**，分三步实施：

### 5.1 增加 Snapshot 存储

在 `SimulationEngine` 的关键操作前后保存当前完整状态：

- `step()` 执行前保存 `R{current_round}` 快照
- `inject_event()` 执行前保存快照（可选，因为事件注入不推进回合）

快照目录：

```
data/snapshots/{simulation_id}/R{round}.json
```

### 5.2 增加回滚 API

```
POST /api/simulations/{id}/rollback?round=5
```

执行逻辑：

1. 加载 `data/snapshots/{id}/R5.json`
2. 替换内存中的 `Simulation` 对象
3. 删除 `R5` 之后的所有 snapshot 文件
4. 更新内存中的轻量 stub
5. 返回恢复后的完整推演状态

### 5.3 前端回溯控件

在推演控制台增加：

- 时间轴滑块或回合选择器
- 显示每回合 `RoundSummary` 摘要
- 确认回滚前的二次确认提示

## 6. 关键注意事项

回溯不是简单修改 `current_round` 字段，必须完整恢复以下状态：

- `agents`（包括每个 Agent 的 `event_log`、`memory`、`sentiment` 等）
- `relations`（全局关系网络）
- `world_state` 和 `world_state_history`
- `timeline`
- `metrics_history`
- `round_summaries`
- `events`
- `topology`

任何字段遗漏都会导致后续推演基于错误的历史继续演化。

## 7. 后续演进方向

如果 Snapshot 方案运行良好，后续可以平滑升级：

1. **Snapshot 压缩**：对旧 snapshot 使用 gzip 压缩，减少磁盘占用
2. **增量 Snapshot**：只保存相邻回合之间的差异
3. **分支推演**：基于某个 snapshot 创建新的推演分支，独立演化
4. **Event Sourcing**：当需要精确审计和反事实分析时，迁移到事件溯源架构

## 8. 待决策事项

- [ ] 是否现在就实现 Snapshot 回溯功能？
- [ ] Snapshot 保存在每次 `step()` 前还是后？
- [ ] 是否需要保留事件注入前的 snapshot？
- [ ] 前端回溯控件采用滑块还是回合列表？
- [ ] 是否允许从中间回合继续推进（默认行为）？
