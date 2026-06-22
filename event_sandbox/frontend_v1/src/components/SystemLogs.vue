<template>
  <div class="system-logs">
    <div class="log-header">
      <span class="log-title">SYSTEM LOGS</span>
      <span class="log-count">{{ logs.length }} 条</span>
    </div>
    <div class="log-content" ref="logContent">
      <div class="log-line" v-for="(log, idx) in logs" :key="idx">
        <span class="log-time">{{ log.time }}</span>
        <span class="log-msg">{{ log.msg }}</span>
      </div>
      <div v-if="logs.length === 0" class="log-empty">等待系统日志...</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  logs: { type: Array, default: () => [] }
})

const logContent = ref(null)

watch(() => props.logs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.system-logs {
  background: #0d1117;
  color: #c9d1d9;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid #21262d;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #21262d;
  padding: 8px 12px;
  font-size: 10px;
  color: #8b949e;
  flex-shrink: 0;
}

.log-title {
  font-weight: 600;
  letter-spacing: 0.5px;
}

.log-count {
  font-size: 10px;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  height: 120px;
  overflow-y: auto;
  padding: 8px 12px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 2px;
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 10px;
  line-height: 1.5;
}

.log-time {
  color: #6e7681;
  min-width: 70px;
  flex-shrink: 0;
}

.log-msg {
  color: #c9d1d9;
  word-break: break-all;
}

.log-empty {
  font-size: 11px;
  color: #6e7681;
  text-align: center;
  padding: 16px 0;
}
</style>
