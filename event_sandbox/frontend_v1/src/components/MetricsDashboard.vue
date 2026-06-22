<template>
  <div class="metrics-dashboard">
    <div class="metrics-header">
      <span class="metrics-title">推演指标</span>
      <span class="metrics-round" v-if="simulation">
        回合 {{ simulation.current_round }} / {{ simulation.rounds }}
      </span>
    </div>
    <div class="metrics-grid" v-if="metrics">
      <div
        class="metric-card"
        v-for="item in metricList"
        :key="item.key"
        @mouseenter="hoveredMetric = item.key"
        @mouseleave="hoveredMetric = null"
      >
        <div class="metric-value" :style="{ color: item.color }">{{ formatValue(metrics[item.key]) }}</div>
        <div class="metric-label">
          {{ item.label }}
          <span class="metric-info">ⓘ</span>
        </div>
        <div class="metric-bar">
          <div class="metric-bar-fill" :style="{ width: `${Math.max(0, Math.min(100, (metrics[item.key] || 0) * 100))}%`, background: item.color }"></div>
        </div>

        <!-- 悬停浮层：含义说明 + 历史折线 -->
        <div v-show="hoveredMetric === item.key" class="metric-tooltip" :style="{ width: chartData[item.key] ? chartData[item.key].tooltipWidth + 'px' : '280px' }">
          <div class="tooltip-desc">{{ item.desc }}</div>
          <div v-if="chartData[item.key]" class="sparkline-wrap">
            <div class="sparkline-scroll">
              <svg :viewBox="chartData[item.key].viewBox" preserveAspectRatio="none" class="sparkline-svg">
                <!-- 水平参考线 -->
                <line :x1="chartData[item.key].plotX" y1="18" :x2="chartData[item.key].plotX + chartData[item.key].plotWidth" y2="18" stroke="#EEE" stroke-width="1" stroke-dasharray="3,3" />
                <line :x1="chartData[item.key].plotX" y1="45" :x2="chartData[item.key].plotX + chartData[item.key].plotWidth" y2="45" stroke="#EEE" stroke-width="1" stroke-dasharray="3,3" />
                <line :x1="chartData[item.key].plotX" y1="72" :x2="chartData[item.key].plotX + chartData[item.key].plotWidth" y2="72" stroke="#EEE" stroke-width="1" stroke-dasharray="3,3" />

                <!-- 折线 -->
                <polyline
                  fill="none"
                  :stroke="item.color"
                  stroke-width="2.5"
                  :points="chartData[item.key].points"
                />

                <!-- 每个点的圆点和数值 -->
                <template v-for="(pt, idx) in chartData[item.key].pointData" :key="idx">
                  <!-- 数值标签：统一在点上方，交错垂直偏移避免重叠 -->
                  <text
                    :x="pt.x"
                    :y="pt.y - (idx % 2 === 0 ? 10 : 18)"
                    text-anchor="middle"
                    font-size="11"
                    font-weight="700"
                    :fill="item.color"
                  >{{ pt.label }}</text>
                  <!-- 圆点 -->
                  <circle :cx="pt.x" :cy="pt.y" r="4" :fill="item.color" />
                </template>

                <!-- X轴回合标注 -->
                <template v-for="(pt, idx) in chartData[item.key].pointData" :key="`x-${idx}`">
                  <text
                    :x="pt.x"
                    y="98"
                    text-anchor="middle"
                    font-size="11"
                    font-weight="600"
                    fill="#999"
                  >R{{ pt.round }}</text>
                </template>
              </svg>
            </div>
            <div class="sparkline-label">历史趋势（{{ historyLength }} 回合）</div>
          </div>
          <div v-else class="sparkline-empty">暂无历史数据</div>
        </div>
      </div>
    </div>
    <div v-else class="metrics-empty">暂无指标数据</div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  simulation: Object,
})

const hoveredMetric = ref(null)

const metrics = computed(() => props.simulation?.metrics)

const metricList = [
  { key: 'network_turbulence', label: '网络动荡度', color: '#e67e22', desc: '本回合发生变更的关系边占比。反映关系网络的重构强度，高值意味着局势剧烈调整。' },
  { key: 'cooperation_level', label: '合作水平', color: '#27ae60', desc: '标注为积极（positive）的关系边占总关系边的比例。' },
  { key: 'conflict_level', label: '冲突程度', color: '#e74c3c', desc: '标注为消极（negative）的关系边占总关系边的比例。' },
  { key: 'action_diversity', label: '行动多样性', color: '#f39c12', desc: '本回合不同行动种类数与实体总数的比值，反映局势复杂度。' },
  { key: 'information_entropy', label: '信息熵', color: '#1abc9c', desc: '基于行动的香农熵。0 表示局势单一，1 表示多方混战。' },
  { key: 'initiative_index', label: '活跃指数', color: '#e67e22', desc: '本回合采取非"观望"行动的实体比例，反映推演活跃度。' },
]

function formatValue(v) {
  if (v === undefined || v === null) return '-'
  return (v * 100).toFixed(1) + '%'
}

function formatLabel(v) {
  if (v === undefined || v === null) return '-'
  return (v * 100).toFixed(0) + '%'
}

// 从历史数据生成图表数据
const historyLength = computed(() => props.simulation?.metrics_history?.length || 0)

const chartData = computed(() => {
  const history = props.simulation?.metrics_history || []
  const result = {}
  if (history.length < 2) return result

  for (const item of metricList) {
    const key = item.key
    const values = history.map(h => h[key] ?? 0)
    const rounds = history.map(h => h.round ?? (h._idx ?? 0) + 1)
    // 指标定义范围固定为 0~1，避免动态缩放导致 99%→100% 看起来像断崖
    const plotMin = 0
    const plotMax = 1
    const range = plotMax - plotMin

    const pointSpacing = 48
    const plotX = 24
    const plotWidth = (values.length - 1) * pointSpacing
    const plotTop = 18
    const plotBottom = 72
    const plotHeight = plotBottom - plotTop
    const svgWidth = plotX + plotWidth + 24
    const svgHeight = 105

    const pointData = values.map((v, i) => {
      const x = plotX + i * pointSpacing
      const clamped = Math.max(plotMin, Math.min(plotMax, v))
      const y = plotBottom - ((clamped - plotMin) / range) * plotHeight
      return {
        x,
        y,
        value: v,
        label: formatLabel(v),
        round: rounds[i] || (i + 1),
      }
    })

    const points = pointData.map(p => `${p.x},${p.y}`).join(' ')
    const tooltipWidth = Math.min(520, Math.max(280, svgWidth))

    result[key] = {
      points,
      pointData,
      viewBox: `0 0 ${svgWidth} ${svgHeight}`,
      plotX,
      plotWidth,
      tooltipWidth,
    }
  }
  return result
})
</script>

<style scoped>
.metrics-dashboard {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 16px;
}

.metrics-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.metrics-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.metrics-round {
  font-size: 12px;
  color: #999;
  font-family: 'JetBrains Mono', monospace;
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.metric-card {
  background: #FAFAFA;
  border-radius: 6px;
  padding: 12px;
  position: relative;
  cursor: default;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  margin-bottom: 4px;
}

.metric-label {
  font-size: 11px;
  color: #888;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.metric-info {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #E0E0E0;
  color: #666;
  font-size: 10px;
  cursor: help;
}

.metric-bar {
  height: 4px;
  background: #E0E0E0;
  border-radius: 2px;
  overflow: hidden;
}

.metric-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* 悬停浮层 */
.metric-tooltip {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 280px;
  max-width: 520px;
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 6px;
  padding: 10px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 50;
  animation: tooltipIn 0.15s ease;
}

@keyframes tooltipIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.tooltip-desc {
  font-size: 11px;
  color: #555;
  line-height: 1.5;
  margin-bottom: 8px;
}

.sparkline-wrap {
  border-top: 1px solid #F0F0F0;
  padding-top: 8px;
}

.sparkline-scroll {
  overflow-x: auto;
  padding-bottom: 4px;
}

.sparkline-scroll::-webkit-scrollbar {
  height: 4px;
}

.sparkline-scroll::-webkit-scrollbar-thumb {
  background: #DDD;
  border-radius: 2px;
}

.sparkline-svg {
  height: 100px;
  display: block;
  min-width: 100%;
}

.sparkline-label {
  font-size: 10px;
  color: #999;
  text-align: center;
  margin-top: 4px;
}

.sparkline-empty {
  font-size: 10px;
  color: #999;
  text-align: center;
  padding: 8px 0;
}

.metrics-empty {
  font-size: 12px;
  color: #999;
  text-align: center;
  padding: 20px 0;
}
</style>
