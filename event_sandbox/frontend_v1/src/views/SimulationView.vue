<template>
  <div class="simulation-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="goHome">EventSandbox</div>
        <span v-if="simulation" class="sim-name">{{ simulation.name }}</span>
      </div>

      <div class="header-center">
        <div class="view-switcher">
          <button
            v-for="mode in viewModes"
            :key="mode.key"
            class="switch-btn"
            :class="{ active: viewMode === mode.key }"
            @click="viewMode = mode.key"
          >
            {{ mode.label }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="time-indicator" v-if="simulation?.config?.round_duration_unit && simulation.config.round_duration_unit !== 'round'">
          {{ formattedSimulatedTime }}
        </div>
        <div class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="content-area">
      <!-- 左侧面板：图谱 -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel
          :graphData="topology"
          :loading="isLoading"
          :agents="agents"
          @refresh="refreshSimulation"
          @node-click="handleNodeClick"
        />
      </div>

      <!-- 右侧面板：控制台 -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <div class="control-panel">
          <!-- 操作栏 -->
          <div class="action-bar">
            <button
              class="primary-btn"
              :disabled="isStepping || isLoading || !canStep"
              @click="handleStep"
            >
              <span v-if="isStepping || (isLoading && !isBatching)" class="spinner-sm"></span>
              {{ isStepping ? '推演进行中...' : (isLoading && !isBatching ? '推进中...' : '推进一回合') }}
            </button>
            <button
              class="secondary-btn"
              :disabled="isStepping || isLoading || !canStep"
              @click="handleBatchStep"
            >
              <span v-if="isBatching" class="spinner-sm"></span>
              批量 {{ batchSteps }} 回合
            </button>
            <button
              v-if="simulation?.status === 'paused'"
              class="secondary-btn"
              @click="handleResume"
            >
              恢复
            </button>
            <button
              v-else-if="simulation?.status === 'running'"
              class="secondary-btn"
              @click="handlePause"
            >
              暂停
            </button>
            <button
              class="secondary-btn"
              :disabled="isGeneratingReport || isGeneratingBaselineReport"
              @click="openReportPanel"
            >
              <span v-if="isGeneratingReport || isGeneratingBaselineReport" class="spinner-sm"></span>
              {{ (isGeneratingReport || isGeneratingBaselineReport) ? '生成中...' : '报告' }}
            </button>
          </div>

          <!-- 批量设置 -->
          <div class="batch-config" v-if="showBatchConfig">
            <label>批量回合数: <input type="number" v-model.number="batchStepsInput" min="1" max="50" /></label>
            <button class="text-btn" @click="showBatchConfig = false">确定</button>
          </div>

          <!-- 世界状态卡片 -->
          <div class="world-state-card" v-if="simulation?.world_state && Object.keys(simulation.world_state).length > 0">
            <div class="world-state-card-header">世界状态</div>
            <div class="world-state-list">
              <div v-for="(value, key) in simulation.world_state" :key="key" class="world-state-row">
                <span class="ws-row-key" :title="key">{{ getWorldStateLabel(key) }}</span>
                <span class="ws-row-value" :title="formatWorldStateValue(value)">{{ formatWorldStateValue(value) }}</span>
              </div>
            </div>
          </div>

          <!-- 指标仪表盘 -->
          <MetricsDashboard :simulation="simulation" />

          <!-- 实体列表 -->
          <div class="agent-list-section">
            <div class="section-header">
              <span class="section-title">实体列表 ({{ agents?.length || 0 }})</span>
              <button class="text-btn" @click="showAgentList = !showAgentList">
                {{ showAgentList ? '收起' : '展开' }}
              </button>
            </div>
            <div v-if="showAgentList" class="agent-list">
              <div
                v-for="agent in agents"
                :key="agent.id"
                class="agent-item"
                :class="{ actionable: agent.is_actionable, inactive: !agent.is_actionable }"
                @click="openAgentDetail(agent)"
              >
                <span class="agent-dot" :style="{ background: getAgentColor(agent.type) }"></span>
                <span class="agent-name">{{ agent.name }}</span>
                <span class="agent-type">{{ agent.type }}</span>
                <span class="agent-sentiment" :class="agent.sentiment > 0 ? 'positive' : 'negative'">
                  {{ (agent.sentiment || 0).toFixed(2) }}
                </span>
              </div>
            </div>
          </div>

          <!-- 推演时间轴 -->
          <ActionTimeline :timeline="simulation?.timeline || []" />

          <!-- 干预面板 -->
          <InterventionPanel
            :isLoading="isLoading"
            :generatingOptions="generatingOptions"
            :eventOptions="generatedEventOptions"
            :optionsError="optionsError"
            @inject-event="handleInjectEvent"
            @add-agent="handleAddAgent"
            @load-options="loadInterventionOptions"
          />
        </div>
      </div>
    </main>

    <!-- 底部日志 -->
    <SystemLogs :logs="logs" />

    <!-- Agent 详情弹窗 -->
    <AgentDetail
      :visible="agentDetailVisible"
      :agent="selectedAgent"
      :relationshipSummary="selectedAgentRelations"
      @close="agentDetailVisible = false"
      @field-change="handleFieldChange"
    />

    <!-- 报告面板 -->
    <ReportPanel
      :visible="reportPanelVisible"
      :report="report"
      :baselineReport="baselineReport"
      :lastAction="lastReportAction"
      :isLoading="isGeneratingReport || isGeneratingBaselineReport"
      @close="reportPanelVisible = false"
      @regenerate="handleGenerateReport"
    />

    <!-- 错误提示 -->
    <div v-if="error" class="error-toast">
      <span>{{ error }}</span>
      <button class="close-btn" @click="clearError">×</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import store from '@/stores/simulationStore'
import * as api from '@/api'
import GraphPanel from '@/components/GraphPanel.vue'
import SystemLogs from '@/components/SystemLogs.vue'
import MetricsDashboard from '@/components/MetricsDashboard.vue'
import ActionTimeline from '@/components/ActionTimeline.vue'
import InterventionPanel from '@/components/InterventionPanel.vue'
import AgentDetail from '@/components/AgentDetail.vue'
import ReportPanel from '@/components/ReportPanel.vue'

const props = defineProps({
  simulationId: String,
})

const router = useRouter()
const route = useRoute()

// 布局
const viewMode = ref('split')
const viewModes = [
  { key: 'graph', label: '图谱' },
  { key: 'split', label: '分栏' },
  { key: 'workbench', label: '工作台' },
]

// 批量配置
const showBatchConfig = ref(false)
const batchStepsInput = ref(5)
const isBatching = ref(false)
const steppingPollTimer = ref(null)

// Agent 详情
const agentDetailVisible = ref(false)
const selectedAgent = ref(null)
const selectedAgentRelations = ref([])
const showAgentList = ref(true)

// 报告面板
const reportPanelVisible = ref(false)
const lastReportAction = ref('')

// 状态
const simulation = computed(() => store.state.simulation)
const agents = computed(() => store.state.agents)
const topology = computed(() => store.state.topology)
const isLoading = computed(() => store.state.isLoading)
const isStepping = computed(() => simulation.value?.is_being_stepped || false)
const error = computed(() => store.state.error)
const logs = computed(() => store.state.logs)
const batchSteps = computed(() => store.state.batchSteps)
const generatingOptions = computed(() => store.state.generatingOptions)
const generatedEventOptions = computed(() => store.state.generatedEventOptions)
const optionsError = computed(() => store.state.optionsError)
const report = computed(() => store.state.report)
const baselineReport = computed(() => store.state.baselineReport)
const isGeneratingReport = computed(() => store.state.isGeneratingReport)
const isGeneratingBaselineReport = computed(() => store.state.isGeneratingBaselineReport)

const canStep = computed(() => {
  if (!simulation.value) return false
  return simulation.value.status !== 'completed' && simulation.value.status !== 'paused'
})

const statusClass = computed(() => {
  if (!simulation.value) return 'pending'
  return simulation.value.status
})

const statusText = computed(() => {
  if (!simulation.value) return '未加载'
  const map = {
    pending: '待启动',
    running: '进行中',
    paused: '已暂停',
    completed: '已完成',
  }
  return map[simulation.value.status] || simulation.value.status
})

const formattedSimulatedTime = computed(() => {
  if (!simulation.value?.current_simulated_time) return ''
  const dt = simulation.value.current_simulated_time
  try {
    const date = new Date(dt)
    if (isNaN(date.getTime())) return ''
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
})

function formatWorldStateValue(value) {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'object') {
    // 对象/数组格式化为可读字符串，例如 {A: 1, B: 2} → "A: 1 | B: 2"
    try {
      const entries = Object.entries(value)
      if (entries.length === 0) return '{}'
      return entries.map(([k, v]) => `${k}: ${v}`).join(' | ')
    } catch {
      return JSON.stringify(value)
    }
  }
  return String(value)
}

function getWorldStateLabel(key) {
  const labels = simulation.value?.world_model?.world_state_labels
  if (labels && labels[key]) {
    return labels[key]
  }
  return key
}

const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1 }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0 }
  return { width: '55%', opacity: 1 }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1 }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0 }
  return { width: '45%', opacity: 1 }
})

// 颜色映射
const agentColorMap = {
  individual: '#FF6B35',
  company: '#004E89',
  government: '#7B2D8E',
  organization: '#1A936F',
  location: '#C5283D',
  military: '#E9724C',
  vehicle: '#3498db',
  entity: '#9b59b6',
}
function getAgentColor(type) {
  return agentColorMap[type] || '#999'
}

function goHome() {
  router.push({ name: 'Home' })
}

async function refreshSimulation() {
  if (!props.simulationId) return
  try {
    await store.getSimulationState(props.simulationId)
  } catch {
    // handled by store
  }
}

async function handleStep() {
  try {
    await store.stepSimulation()
  } catch {
    // handled by store
  }
}

async function handleBatchStep() {
  isBatching.value = true
  try {
    await store.batchStep(batchStepsInput.value)
  } catch {
    // handled by store
  } finally {
    isBatching.value = false
  }
}

async function handlePause() {
  await store.pauseSimulation()
}

async function handleResume() {
  await store.resumeSimulation()
}

// 报告面板

async function openReportPanel() {
  reportPanelVisible.value = true
  // 进入面板时自动尝试加载已保存报告
  if (!store.state.report && !store.state.baselineReport) {
    try {
      await store.getReport()
    } catch {
      // handled by store
    }
  }
}

async function handleGenerateReport(type = 'graph') {
  lastReportAction.value = type
  try {
    if (type === 'graph') {
      await store.generateReport()
    } else if (type === 'baseline') {
      await store.generateBaselineReport()
    } else if (type === 'both') {
      await Promise.all([
        store.generateReport(),
        store.generateBaselineReport(),
      ])
    }
  } catch {
    // handled by store
  }
}

async function handleRegenerateReport(type = 'graph') {
  await handleGenerateReport(type === 'baseline' ? 'baseline' : 'graph')
}

async function handleInjectEvent(data) {
  try {
    await store.injectEvent(data.description)
  } catch {
    // handled by store
  }
}

async function handleAddAgent(data) {
  try {
    await store.addAgent(data)
  } catch {
    // handled by store
  }
}

async function loadInterventionOptions() {
  await store.loadGlobalInterventionOptions()
}

async function openAgentDetail(agent) {
  selectedAgent.value = agent
  if (simulation.value?.relations) {
    selectedAgentRelations.value = simulation.value.relations
      .filter(r => r.source_id === agent.id || r.target_id === agent.id)
      .map(r => ({
        target_id: r.source_id === agent.id ? r.target_id : r.source_id,
        target_name: agents.value.find(a => a.id === (r.source_id === agent.id ? r.target_id : r.source_id))?.name || '未知',
        relation: r.relation,
        description: r.description,
      }))
  } else {
    selectedAgentRelations.value = []
  }
  agentDetailVisible.value = true
}

function handleNodeClick(nodeData) {
  const agent = agents.value.find(a => a.id === nodeData.id || nodeData.agent_id === a.id)
  if (agent) {
    openAgentDetail(agent)
  }
}

async function handleFieldChange({ agent_id, field, value }) {
  try {
    await api.modifyAgent(simulation.value.id, agent_id, { field, value })
    store.addLog(`已修改实体 ${agent_id} 的 ${field}`)
    await refreshSimulation()
  } catch (err) {
    store.setError(err.message || '修改失败')
  }
}

function clearError() {
  store.clearError()
}

watch(batchStepsInput, (v) => {
  store.setBatchSteps(v)
})

// 当后端显示推演正在执行时，轮询刷新状态，直到执行完成
watch(isStepping, (stepping) => {
  if (stepping) {
    if (steppingPollTimer.value) return
    steppingPollTimer.value = setInterval(() => {
      if (props.simulationId) {
        refreshSimulation()
      }
    }, 2500)
  } else {
    if (steppingPollTimer.value) {
      clearInterval(steppingPollTimer.value)
      steppingPollTimer.value = null
    }
  }
})

onMounted(() => {
  if (props.simulationId) {
    refreshSimulation()
  }
})

onUnmounted(() => {
  if (steppingPollTimer.value) {
    clearInterval(steppingPollTimer.value)
    steppingPollTimer.value = null
  }
})
</script>

<style scoped>
.simulation-view {
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
  min-width: 0;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  color: #000;
  cursor: pointer;
  flex-shrink: 0;
}

.sim-name {
  font-size: 14px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.view-switcher {
  display: flex;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: #000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.world-state-card {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.world-state-card-header {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.world-state-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.world-state-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  font-size: 12px;
  line-height: 1.4;
}

.ws-row-key {
  color: #999;
  flex-shrink: 0;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-row-value {
  color: #333;
  font-weight: 600;
  text-align: right;
  word-break: break-all;
}

.time-indicator {
  font-size: 13px;
  color: #666;
  font-family: 'JetBrains Mono', monospace;
  background: #F5F5F5;
  padding: 4px 10px;
  border-radius: 4px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #999;
  font-weight: 500;
}

.status-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.running .dot {
  background: #4CAF50;
  animation: pulse 1.5s infinite;
}

.status-indicator.paused .dot {
  background: #FF9800;
}

.status-indicator.completed .dot {
  background: #9E9E9E;
}

.status-indicator.running,
.status-indicator.paused {
  color: #333;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.tool-btn {
  height: 32px;
  padding: 0 10px;
  border: 1px solid #E0E0E0;
  background: #FFF;
  border-radius: 6px;
  cursor: pointer;
  color: #666;
  font-size: 14px;
  transition: all 0.2s;
}

.tool-btn:hover {
  background: #F5F5F5;
}

.tool-btn .spinning {
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin { to { transform: rotate(360deg); } }

.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease;
  will-change: width, opacity;
}

.panel-wrapper.left {
  border-right: 1px solid #EAEAEA;
}

.panel-wrapper.right {
  overflow-y: auto;
}

.control-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.primary-btn,
.secondary-btn {
  flex: 1;
  min-width: 100px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
}

.primary-btn {
  background: #000;
  color: #FFF;
}

.primary-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.secondary-btn {
  background: #FFF;
  color: #333;
  border: 1px solid #E0E0E0;
}

.secondary-btn:hover:not(:disabled) {
  background: #F5F5F5;
}

.primary-btn:disabled,
.secondary-btn:disabled {
  background: #E0E0E0;
  color: #999;
  cursor: not-allowed;
  border-color: #E0E0E0;
}

.spinner-sm {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.batch-config {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #666;
  background: #FAFAFA;
  padding: 8px 12px;
  border-radius: 6px;
}

.batch-config input {
  width: 60px;
  padding: 4px 8px;
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  font-size: 12px;
}

.text-btn {
  background: none;
  border: none;
  font-size: 12px;
  color: #666;
  cursor: pointer;
  padding: 0;
  font-weight: 500;
}

.text-btn:hover {
  color: #000;
}

.agent-list-section {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 12px 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.agent-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 12px;
}

.agent-item:hover {
  background: #F5F5F5;
}

.agent-item.inactive {
  opacity: 0.6;
}

.agent-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.agent-name {
  font-weight: 500;
  color: #333;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.agent-type {
  font-size: 10px;
  color: #999;
  background: #F0F0F0;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.agent-sentiment {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
}

.agent-sentiment.positive {
  color: #27ae60;
}

.agent-sentiment.negative {
  color: #e74c3c;
}

.error-toast {
  position: fixed;
  bottom: 140px;
  left: 50%;
  transform: translateX(-50%);
  background: #FFEBEE;
  color: #C62828;
  border: 1px solid #EF9A9A;
  padding: 10px 16px;
  border-radius: 6px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 200;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.error-toast .close-btn {
  background: none;
  border: none;
  font-size: 16px;
  color: #C62828;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}
</style>
