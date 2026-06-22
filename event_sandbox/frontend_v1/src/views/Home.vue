<template>
  <div class="home-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand">EventSandbox</div>
        <span class="brand-sub">智能事件推演沙盘</span>
      </div>
      <div class="header-right">
        <div class="status-indicator" :class="{ healthy: backendHealthy }">
          <span class="dot"></span>
          {{ backendHealthy ? '后端正常' : '后端未连接' }}
        </div>
        <div class="status-indicator" :class="{ healthy: llmConnected }">
          <span class="dot"></span>
          {{ llmConnected ? 'LLM 已连接' : 'LLM 未连接' }}
        </div>
      </div>
    </header>

    <main class="home-main">
      <!-- 左侧：创建表单 -->
      <div class="create-panel">
        <div class="panel-card">
          <h2 class="card-title">创建推演场景</h2>
          <p class="card-desc">输入事件描述，系统将自动提取实体并构建推演图谱</p>

          <div class="form-group">
            <label>推演名称</label>
            <input v-model="form.name" type="text" placeholder="例如：中美科技竞争推演" />
          </div>

          <div class="form-group">
            <label>推演描述（可选）</label>
            <input v-model="form.description" type="text" placeholder="简要描述推演背景..." />
          </div>

          <div class="form-group">
            <label>事件文本</label>
            <textarea
              v-model="form.event_text"
              rows="6"
              placeholder="输入详细的初始事件描述。系统将从中提取实体、构建关系网络..."
            ></textarea>
          </div>

          <div class="form-group">
            <label>推演主线（可选）</label>
            <input
              v-model="form.config.main_line"
              type="text"
              placeholder="输入主线目标，例如：美伊双方接下来的军事行动与外交博弈"
            />
            <span class="field-hint">设置主线后，Agent 决策会更倾向于推动该方向发展</span>
          </div>

          <div class="form-row">
            <div class="form-group half">
              <label>推演回合数</label>
              <input v-model.number="form.rounds" type="number" min="1" max="100" />
            </div>
            <div class="form-group half">
              <label>LLM 模型</label>
              <input v-model="form.config.llm_model" type="text" placeholder="默认使用后端配置" />
            </div>
          </div>

          <div class="form-section">
            <div class="section-title">时间切片配置</div>
            <div class="form-row">
              <div class="form-group half">
                <label>起始时间</label>
                <input v-model="form.config.start_datetime" type="datetime-local" />
              </div>
              <div class="form-group half">
                <label>每回合时长</label>
                <div class="duration-row">
                  <input v-model.number="form.config.round_duration_value" type="number" min="0.1" step="0.1" class="duration-value" />
                  <select v-model="form.config.round_duration_unit" class="duration-unit">
                    <option value="round">回合（无时间语义）</option>
                    <option value="minute">分钟</option>
                    <option value="hour">小时</option>
                    <option value="day">天</option>
                    <option value="week">周</option>
                    <option value="month">月</option>
                    <option value="quarter">季度</option>
                    <option value="year">年</option>
                  </select>
                </div>
              </div>
            </div>
            <span class="field-hint">设置后不可修改。例如：足球比赛 90 分钟分 10 回合，则每回合 9 分钟；美伊冲突可设为每回合 1 天。</span>
          </div>

          <button
            class="create-btn"
            :disabled="!canCreate || isLoading"
            @click="handleCreate"
          >
            <span v-if="isLoading" class="spinner-sm"></span>
            {{ isLoading ? '构建中...' : '创建推演' }}
          </button>
          <div v-if="error" class="create-error">创建失败：{{ error }}</div>
        </div>
      </div>

      <!-- 右侧：历史列表 + 系统日志 -->
      <div class="side-panel">
        <div class="panel-card history-card">
          <div class="card-header-row">
            <h3 class="card-subtitle">历史推演</h3>
            <button class="refresh-btn" @click="loadHistory" :disabled="loadingHistory">
              <span :class="{ spinning: loadingHistory }">↻</span>
            </button>
          </div>
          <div v-if="history.length" class="history-list">
            <div
              v-for="item in history"
              :key="item.id"
              class="history-item"
              @click="goToSimulation(item.id)"
            >
              <div class="history-info">
                <span class="history-name">{{ item.name }}</span>
                <span class="history-meta">
                  回合 {{ item.current_round }}/{{ item.rounds }} · {{ item.agent_count }} 实体 · {{ item.status }}
                </span>
              </div>
              <button
                class="delete-btn"
                @click.stop="handleDelete(item.id)"
                title="删除"
              >
                ×
              </button>
            </div>
          </div>
          <div v-else class="history-empty">暂无推演记录</div>
        </div>
      </div>
    </main>

    <!-- 底部日志 -->
    <SystemLogs :logs="logs" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import store from '@/stores/simulationStore'
import { listSimulations } from '@/api'
import SystemLogs from '@/components/SystemLogs.vue'

const router = useRouter()

const form = ref({
  name: '',
  description: '',
  event_text: '',
  rounds: 10,
  config: {
    llm_model: '',
    main_line: '',
    start_datetime: '',
    round_duration_value: 1,
    round_duration_unit: 'round',
  },
})

const history = ref([])
const loadingHistory = ref(false)

const isLoading = computed(() => store.state.isLoading)
const backendHealthy = computed(() => store.state.backendHealthy)
const llmConnected = computed(() => store.state.llmConnected)
const logs = computed(() => store.state.logs)

          const error = computed(() => store.state.error)

const canCreate = computed(() => {
  return form.value.name.trim() && form.value.event_text.trim()
})

async function handleCreate() {
  const config = {}
  if (form.value.config.llm_model) {
    config.llm_model = form.value.config.llm_model
  }
  if (form.value.config.main_line?.trim()) {
    config.main_line = form.value.config.main_line.trim()
  }
  // 时间切片配置
  if (form.value.config.start_datetime) {
    config.start_datetime = new Date(form.value.config.start_datetime).toISOString()
  }
  if (form.value.config.round_duration_value) {
    config.round_duration_value = form.value.config.round_duration_value
  }
  if (form.value.config.round_duration_unit) {
    config.round_duration_unit = form.value.config.round_duration_unit
  }
  try {
    const data = await store.createSimulation(
      form.value.name,
      form.value.description,
      form.value.event_text,
      form.value.rounds,
      Object.keys(config).length ? config : undefined
    )
    router.push({ name: 'Simulation', params: { simulationId: data.simulation.id } })
  } catch {
    // error handled by store
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const data = await listSimulations({ limit: 20 })
    history.value = data.simulations || []
    store.addLog(`加载历史推演: ${history.value.length} 条`)
  } catch (err) {
    store.setError(err.message || '加载历史失败')
  } finally {
    loadingHistory.value = false
  }
}

function goToSimulation(id) {
  router.push({ name: 'Simulation', params: { simulationId: id } })
}

async function handleDelete(id) {
  if (!confirm('确定删除该推演？')) return
  await store.deleteSimulation(id)
  await loadHistory()
}

onMounted(() => {
  store.checkHealth()
  loadHistory()
})
</script>

<style scoped>
.home-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #F5F5F5;
  overflow: hidden;
  font-family: 'Noto Sans SC', system-ui, sans-serif;
}

.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #FFF;
  z-index: 100;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  color: #000;
}

.brand-sub {
  font-size: 12px;
  color: #999;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #999;
}

.status-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.healthy .dot {
  background: #4CAF50;
}

.status-indicator.healthy {
  color: #333;
}

.home-main {
  flex: 1;
  display: flex;
  gap: 20px;
  padding: 24px;
  overflow: hidden;
}

.create-panel {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}

.side-panel {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
}

.panel-card {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 24px;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
  color: #333;
  margin-bottom: 4px;
}

.card-desc {
  font-size: 13px;
  color: #999;
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: #555;
}

.form-group input,
.form-group textarea,
.form-group select {
  padding: 10px 12px;
  border: 1px solid #E0E0E0;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  background: #FAFAFA;
  transition: border-color 0.2s;
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: #999;
}

.field-hint {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.form-row {
  display: flex;
  gap: 12px;
}

.form-group.half {
  flex: 1;
  margin-bottom: 0;
}

.create-btn {
  width: 100%;
  background: #000;
  color: #FFF;
  border: none;
  padding: 14px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
}

.create-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.create-btn:disabled {
  background: #CCC;
  cursor: not-allowed;
}

.create-error {
  margin-top: 12px;
  padding: 10px 12px;
  background: #FDECEA;
  border: 1px solid #F5C6CB;
  border-radius: 6px;
  color: #C0392B;
  font-size: 13px;
  line-height: 1.5;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #FFF;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.refresh-btn {
  background: none;
  border: none;
  font-size: 16px;
  color: #999;
  cursor: pointer;
  padding: 4px;
  transition: color 0.2s;
}

.refresh-btn:hover {
  color: #333;
}

.refresh-btn .spinning {
  animation: spin 1s linear infinite;
  display: inline-block;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #FAFAFA;
  border: 1px solid #F0F0F0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  background: #F0F0F0;
  border-color: #E0E0E0;
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.history-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-meta {
  font-size: 11px;
  color: #999;
  font-family: 'JetBrains Mono', monospace;
}

.delete-btn {
  background: none;
  border: none;
  font-size: 18px;
  color: #CCC;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  transition: color 0.2s;
}

.delete-btn:hover {
  color: #e74c3c;
}

.history-empty {
  font-size: 12px;
  color: #999;
  text-align: center;
  padding: 20px 0;
}
</style>
