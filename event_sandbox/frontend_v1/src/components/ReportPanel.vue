<template>
  <div v-if="visible" class="report-overlay" @click.self="close">
    <div class="report-panel">
      <div class="report-header">
        <h2 class="report-title">推演分析报告</h2>
        <div class="header-actions">
          <template v-if="showComparison">
            <button
              v-if="report && !isLoading"
              class="regenerate-btn"
              @click="regenerate('graph')"
            >
              重新生成推演
            </button>
            <button
              v-if="baselineReport && !isLoading"
              class="regenerate-btn"
              @click="regenerate('baseline')"
            >
              重新生成基线
            </button>
          </template>
          <button
            v-else-if="(report || baselineReport) && !isLoading"
            class="regenerate-btn"
            @click="regenerate(viewMode === 'baseline' ? 'baseline' : 'graph')"
          >
            重新生成
          </button>
          <button class="close-btn" @click="close">×</button>
        </div>
      </div>

      <div class="report-body">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="report-loading">
          <div class="spinner"></div>
          <p>正在生成报告，请稍候...</p>
          <p class="hint">基于推演数据进行深度分析</p>
        </div>

        <!-- 报告内容 -->
        <div v-else-if="report || baselineReport" class="report-content">
          <!-- Tab 切换 -->
          <div class="report-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="tab-btn"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>

          <!-- 视图模式切换（仅当两份报告都存在时显示） -->
          <div v-if="canSwitchView" class="view-mode-bar">
            <button
              v-for="vm in viewModes"
              :key="vm.key"
              class="vm-btn"
              :class="{ active: viewMode === vm.key }"
              @click="viewMode = vm.key"
            >
              {{ vm.label }}
            </button>
          </div>

          <!-- 1. Agent 分析 -->
          <div v-if="activeTab === 'agents'" class="tab-content">
            <template v-if="showComparison">
              <div class="comparison-grid">
                <div class="report-col">
                  <div class="col-header">推演报告（基于图谱）</div>
                  <div v-if="report?.agent_summaries?.length" class="agent-summaries">
                    <div v-for="(s, idx) in report.agent_summaries" :key="idx" class="agent-summary-card">
                      <h4 class="agent-name">{{ s.agent_name }}</h4>
                      <p class="agent-summary-text">{{ s.summary }}</p>
                    </div>
                  </div>
                  <div v-else class="empty-text">暂无 Agent 分析</div>
                </div>
                <div class="report-col">
                  <div class="col-header">基线报告（纯 LLM）</div>
                  <div v-if="baselineReport?.agent_summaries?.length" class="agent-summaries">
                    <div v-for="(s, idx) in baselineReport.agent_summaries" :key="idx" class="agent-summary-card">
                      <h4 class="agent-name">{{ s.agent_name }}</h4>
                      <p class="agent-summary-text">{{ s.summary }}</p>
                    </div>
                  </div>
                  <div v-else class="empty-text">暂无 Agent 分析</div>
                </div>
              </div>
            </template>
            <template v-else>
              <div v-if="activeSingleReport?.agent_summaries?.length" class="agent-summaries">
                <div v-for="(s, idx) in activeSingleReport.agent_summaries" :key="idx" class="agent-summary-card">
                  <h4 class="agent-name">{{ s.agent_name }}</h4>
                  <p class="agent-summary-text">{{ s.summary }}</p>
                </div>
              </div>
              <div v-else class="empty-text">暂无 Agent 分析</div>
            </template>
          </div>

          <!-- 2. 整体总结 -->
          <div v-if="activeTab === 'overall'" class="tab-content">
            <template v-if="showComparison">
              <div class="comparison-grid">
                <div class="report-col">
                  <div class="col-header">推演报告（基于图谱）</div>
                  <div v-if="report?.overall_summary" class="summary-text">{{ report.overall_summary }}</div>
                  <div v-else class="empty-text">暂无整体总结</div>
                </div>
                <div class="report-col">
                  <div class="col-header">基线报告（纯 LLM）</div>
                  <div v-if="baselineReport?.overall_summary" class="summary-text">{{ baselineReport.overall_summary }}</div>
                  <div v-else class="empty-text">暂无整体总结</div>
                </div>
              </div>
            </template>
            <template v-else>
              <div v-if="activeSingleReport?.overall_summary" class="summary-text">{{ activeSingleReport.overall_summary }}</div>
              <div v-else class="empty-text">暂无整体总结</div>
            </template>
          </div>

          <!-- 3. 结论 -->
          <div v-if="activeTab === 'conclusion'" class="tab-content">
            <template v-if="showComparison">
              <div class="comparison-grid">
                <div class="report-col">
                  <div class="col-header">推演报告（基于图谱）</div>
                  <div v-if="report?.conclusion" class="conclusion-text">{{ report.conclusion }}</div>
                  <div v-else class="empty-text">暂无结论</div>
                </div>
                <div class="report-col">
                  <div class="col-header">基线报告（纯 LLM）</div>
                  <div v-if="baselineReport?.conclusion" class="conclusion-text">{{ baselineReport.conclusion }}</div>
                  <div v-else class="empty-text">暂无结论</div>
                </div>
              </div>
            </template>
            <template v-else>
              <div v-if="activeSingleReport?.conclusion" class="conclusion-text">{{ activeSingleReport.conclusion }}</div>
              <div v-else class="empty-text">暂无结论</div>
            </template>
          </div>

          <!-- 4. 完整报告 -->
          <div v-if="activeTab === 'full'" class="tab-content">
            <template v-if="showComparison">
              <div class="comparison-grid">
                <div class="report-col">
                  <div class="col-header">推演报告（基于图谱）</div>
                  <div class="full-report markdown-body" v-html="renderMarkdown(report?.full_report)"></div>
                </div>
                <div class="report-col">
                  <div class="col-header">基线报告（纯 LLM）</div>
                  <div class="full-report markdown-body" v-html="renderMarkdown(baselineReport?.full_report)"></div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="full-report markdown-body" v-html="renderMarkdown(activeSingleReport?.full_report)"></div>
            </template>
          </div>
        </div>

        <div v-else class="report-empty">
          <p>尚未生成报告</p>
          <div class="report-empty-actions">
            <button class="primary-btn" @click="regenerate('graph')">生成推演报告</button>
            <button class="primary-btn" @click="regenerate('baseline')">生成基线报告</button>
            <button class="primary-btn" @click="regenerate('both')">同时生成两者</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  visible: Boolean,
  report: Object,
  baselineReport: Object,
  isLoading: Boolean,
  lastAction: { type: String, default: '' },
})

const emit = defineEmits(['close', 'regenerate'])

const activeTab = ref('agents')

const tabs = [
  { key: 'agents', label: 'Agent 分析' },
  { key: 'overall', label: '整体总结' },
  { key: 'conclusion', label: '结论' },
  { key: 'full', label: '完整报告' },
]

const viewModes = [
  { key: 'graph', label: '推演报告' },
  { key: 'baseline', label: '基线报告' },
  { key: 'compare', label: '对比' },
]

// 视图模式：graph | baseline | compare
const viewMode = ref('graph')

// 根据 lastAction 初始化视图模式（不依赖数据是否已到达，避免异步延迟导致误判）
function initViewMode() {
  if (props.lastAction === 'baseline') {
    viewMode.value = 'baseline'
  } else if (props.lastAction === 'both') {
    viewMode.value = 'compare'
  } else {
    viewMode.value = 'graph'
  }
}
initViewMode()

const showComparison = computed(() => viewMode.value === 'compare')
const canSwitchView = computed(() => !!props.report && !!props.baselineReport)

// 单栏模式下当前展示的报告
const activeSingleReport = computed(() => {
  if (viewMode.value === 'baseline') return props.baselineReport
  return props.report
})

function close() {
  emit('close')
}

function regenerate(type = 'graph') {
  emit('regenerate', type)
}

function renderMarkdown(text) {
  if (!text) return '<p>无内容</p>'
  return marked.parse(text, {
    gfm: true,
    breaks: true,
    headerIds: false,
  })
}
</script>

<style scoped>
.report-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.report-panel {
  background: #FFF;
  border-radius: 10px;
  width: 900px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #EAEAEA;
  background: #FAFAFA;
  flex-shrink: 0;
}

.report-title {
  font-size: 16px;
  font-weight: 700;
  color: #333;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #999;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #F0F0F0;
  color: #333;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.regenerate-btn {
  background: #FFF;
  border: 1px solid #E0E0E0;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.regenerate-btn:hover {
  background: #F5F5F5;
  color: #000;
}

.report-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.report-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  gap: 12px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #E0E0E0;
  border-top-color: #333;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.hint {
  font-size: 12px;
  color: #999;
}

.report-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
  border-bottom: 1px solid #EAEAEA;
  padding-bottom: 8px;
}

.view-mode-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
}

.vm-btn {
  border: 1px solid #E0E0E0;
  background: #FFF;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 500;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.vm-btn.active {
  background: #333;
  color: #FFF;
  border-color: #333;
}

.vm-btn:hover:not(.active) {
  background: #F5F5F5;
}

.tab-btn {
  border: none;
  background: transparent;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: #000;
  color: #FFF;
}

.tab-btn:hover:not(.active) {
  background: #F5F5F5;
}

.tab-content {
  font-size: 13px;
  line-height: 1.7;
  color: #444;
}

/* 对比视图网格 */
.comparison-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.report-col {
  background: #FAFAFA;
  border-radius: 8px;
  border: 1px solid #F0F0F0;
  overflow: hidden;
}

.col-header {
  font-size: 12px;
  font-weight: 600;
  color: #555;
  padding: 10px 12px;
  background: #F0F0F0;
  border-bottom: 1px solid #EAEAEA;
}

.col-body {
  padding: 12px;
}

/* 关键点 */
.agent-summaries {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.agent-summary-card {
  padding: 12px;
  background: #FFF;
  border-radius: 6px;
}

.agent-name {
  font-size: 13px;
  font-weight: 700;
  color: #333;
  margin: 0 0 6px 0;
}

.agent-summary-text {
  margin: 0;
  color: #555;
}

/* 文本块 */
.summary-text,
.conclusion-text {
  white-space: pre-wrap;
  padding: 12px;
}

/* 完整报告 */
.full-report {
  font-family: 'Noto Sans SC', system-ui, sans-serif;
  font-size: 13px;
  line-height: 1.7;
  color: #444;
  background: #FFF;
  padding: 12px;
  overflow-x: auto;
}

/* Markdown 渲染样式 */
.markdown-body :deep(h1) {
  font-size: 16px;
  font-weight: 700;
  color: #333;
  margin: 16px 0 8px 0;
  padding-bottom: 6px;
  border-bottom: 1px solid #EAEAEA;
}

.markdown-body :deep(h2) {
  font-size: 14px;
  font-weight: 700;
  color: #333;
  margin: 14px 0 8px 0;
}

.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  font-size: 13px;
  font-weight: 600;
  color: #444;
  margin: 12px 0 6px 0;
}

.markdown-body :deep(p) {
  margin: 8px 0;
  color: #444;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 3px solid #DDD;
  background: #FAFAFA;
  color: #666;
}

.markdown-body :deep(code) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: #F5F5F5;
  padding: 2px 5px;
  border-radius: 3px;
  color: #C62828;
}

.markdown-body :deep(pre) {
  background: #F8F8F8;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 10px 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #444;
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: #333;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #EAEAEA;
  margin: 12px 0;
}

.empty-text {
  font-size: 13px;
  color: #999;
  text-align: center;
  padding: 20px 0;
}

.report-empty {
  text-align: center;
  padding: 40px 0;
  color: #999;
}

.report-empty p {
  margin: 0 0 16px 0;
}

.report-empty-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.generate-options {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.report-empty-actions .secondary-btn,
.report-empty-actions .primary-btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 14px;
}

.report-empty-actions .secondary-btn {
  background: #f0f0f0;
  color: #333;
}

.report-empty-actions .secondary-btn:hover {
  background: #e0e0e0;
}

.report-empty-actions .primary-btn {
  background: #1A936F;
  color: #fff;
}

.report-empty-actions .primary-btn:hover {
  background: #157a5c;
}
</style>
