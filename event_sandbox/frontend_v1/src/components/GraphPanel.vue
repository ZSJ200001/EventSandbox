<template>
  <div class="graph-panel">
    <div class="panel-header">
      <span class="panel-title">知识图谱</span>
      <div class="header-tools">
        <button class="tool-btn" @click="$emit('refresh')" :disabled="loading" title="刷新图谱">
          <span class="icon-refresh" :class="{ 'spinning': loading }">↻</span>
          <span class="btn-text">刷新</span>
        </button>
        <button class="tool-btn" @click="resetZoom" title="重置视图">
          <span>⌖</span>
          <span class="btn-text">重置</span>
        </button>
        <label class="edge-labels-toggle">
          <span class="toggle-switch">
            <input type="checkbox" v-model="showEdgeLabels" />
            <span class="slider"></span>
          </span>
          <span class="toggle-label">显示关系标签</span>
        </label>
      </div>
    </div>

    <div class="graph-container" ref="graphContainer">
      <div v-if="graphData && hasNodes" class="graph-view">
        <svg ref="graphSvg" class="graph-svg"></svg>

        <!-- 详情面板 -->
        <div v-if="selectedItem" class="detail-panel">
          <div class="detail-panel-header">
            <span class="detail-title">{{ selectedItem.type === 'node' ? '节点详情' : '关系详情' }}</span>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
              {{ selectedItem.entityType }}
            </span>
            <button class="detail-close" @click="closeDetailPanel">×</button>
          </div>

          <!-- 节点详情 -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">名称:</span>
              <span class="detail-value">{{ selectedItem.data.label }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">ID:</span>
              <span class="detail-value uuid-text">{{ selectedItem.data.id }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">类型:</span>
              <span class="detail-value">{{ selectedItem.data.node_type }}</span>
            </div>

            <!-- 元数据 -->
            <div class="detail-section" v-if="nodeMetadataKeys.length > 0">
              <div class="section-title">属性:</div>
              <div class="properties-list">
                <div v-for="key in nodeMetadataKeys" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ formatMetadataValue(selectedItem.data.metadata?.[key]) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 边详情 -->
          <div v-else class="detail-content">
            <div class="edge-relation-header">
              {{ selectedItem.sourceName }} → {{ selectedItem.data.relation || selectedItem.data.label || '关联' }} → {{ selectedItem.targetName }}
            </div>

            <div class="detail-row" v-if="selectedItem.data.description">
              <span class="detail-label">描述:</span>
              <span class="detail-value fact-text">{{ selectedItem.data.description }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">类型:</span>
              <span class="detail-value">{{ selectedItem.data.edge_type || '未知' }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.round !== undefined && selectedItem.data.round !== null">
              <span class="detail-label">创建回合:</span>
              <span class="detail-value">{{ selectedItem.data.round }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.last_interaction_round !== undefined && selectedItem.data.last_interaction_round !== null">
              <span class="detail-label">最近更新:</span>
              <span class="detail-value">R{{ selectedItem.data.last_interaction_round }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.interaction_count">
              <span class="detail-label">交互次数:</span>
              <span class="detail-value">{{ selectedItem.data.interaction_count }}</span>
            </div>

            <!-- 演变历史 -->
            <div class="detail-section" v-if="selectedItem.evolutionHistory && selectedItem.evolutionHistory.length > 1">
              <div class="section-title">演变历史</div>
              <div class="evolution-list">
                <div v-for="(item, idx) in selectedItem.evolutionHistory" :key="idx" class="evolution-item">
                  <div class="evolution-round">R{{ item.round }}</div>
                  <div class="evolution-body">
                    <div class="evolution-relation">{{ item.relation }}</div>
                    <div class="evolution-desc" v-if="item.description">{{ item.description }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>图谱加载中...</p>
      </div>

      <div v-else class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">暂无图谱数据</p>
      </div>
    </div>

    <!-- 底部图例 -->
    <div v-if="graphData && hasNodes && entityTypes.length" class="graph-legend">
      <span class="legend-title">实体类型</span>
      <div class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ type.name }}</span>
        </div>
      </div>
    </div>

    <!-- 过滤与回放工具栏 -->
    <div v-if="graphData && hasNodes" class="graph-toolbar">
      <div class="toolbar-group">
        <span class="toolbar-label">显示:</span>
        <select v-model="filterMode" class="toolbar-select">
          <option value="all">全部关系</option>
          <option value="current">只看本回合</option>
          <option value="recent">最近 N 回合</option>
        </select>
        <select v-if="filterMode === 'recent'" v-model="recentNRounds" class="toolbar-select">
          <option :value="1">1 回合</option>
          <option :value="2">2 回合</option>
          <option :value="3">3 回合</option>
          <option :value="5">5 回合</option>
        </select>
      </div>
      <div class="toolbar-group">
        <span class="toolbar-label">回放:</span>
        <input
          type="range"
          v-model="replayRound"
          :min="0"
          :max="maxRound"
          class="replay-slider"
        />
        <span class="replay-label">R{{ replayRound }}</span>
        <button class="toolbar-btn" @click="toggleReplay">{{ isReplaying ? '暂停' : '播放' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  agents: { type: Array, default: () => [] },
})

const emit = defineEmits(['refresh', 'edit-agent'])

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true)
const filterMode = ref('all')
const recentNRounds = ref(3)
const replayRound = ref(0)
const isReplaying = ref(false)
let replayTimer = null

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null
let zoomBehavior = null

const hasNodes = computed(() => {
  return props.graphData?.nodes?.length > 0
})

const maxRound = computed(() => {
  const current = props.graphData?.metadata?.current_round || 0
  const maxFromEdges = props.graphData?.edges?.reduce((max, e) => {
    return Math.max(max, e.last_interaction_round || 0, e.round || 0)
  }, 0) || 0
  return Math.max(current, maxFromEdges)
})

watch(() => props.graphData, () => {
  replayRound.value = maxRound.value
  nextTick(renderGraph)
}, { deep: true })
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  const colors = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']

  props.graphData.nodes.forEach(node => {
    const type = node.metadata?.agent_type || node.node_type || 'unknown'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: colors[Object.keys(typeMap).length % colors.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

const nodeMetadataKeys = computed(() => {
  if (!selectedItem.value || selectedItem.value.type !== 'node') return []
  const metadata = selectedItem.value.data.metadata || {}
  return Object.keys(metadata).filter(k => metadata[k] !== undefined && metadata[k] !== null)
})

function formatMetadataValue(v) {
  if (v === null || v === undefined) return 'None'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function closeDetailPanel() {
  selectedItem.value = null
}

function resetZoom() {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)
  svg.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity)
}

function getFilteredEdges() {
  if (!props.graphData?.edges) return []
  const currentRound = props.graphData?.metadata?.current_round || maxRound.value

  return props.graphData.edges.filter(e => {
    // 回放过滤：只显示创建回合 <= replayRound 的边
    if ((e.round || 0) > replayRound.value) return false

    // 模式过滤
    if (filterMode.value === 'current') {
      return (e.last_interaction_round || 0) === currentRound
    }
    if (filterMode.value === 'recent') {
      return (e.last_interaction_round || 0) >= currentRound - recentNRounds.value + 1
    }
    return true
  })
}

function toggleReplay() {
  if (isReplaying.value) {
    clearInterval(replayTimer)
    replayTimer = null
    isReplaying.value = false
  } else {
    replayRound.value = 0
    isReplaying.value = true
    replayTimer = setInterval(() => {
      if (replayRound.value >= maxRound.value) {
        clearInterval(replayTimer)
        replayTimer = null
        isReplaying.value = false
      } else {
        replayRound.value++
      }
    }, 1000)
  }
}

watch([filterMode, recentNRounds, replayRound], () => {
  nextTick(renderGraph)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (currentSimulation) currentSimulation.stop()
  if (replayTimer) clearInterval(replayTimer)
})
const renderGraph = () => {
  if (!graphSvg.value || !props.graphData || !hasNodes.value) return

  if (currentSimulation) {
    currentSimulation.stop()
  }

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  svg.selectAll('*').remove()

  const nodesData = props.graphData.nodes || []
  const edgesData = getFilteredEdges()

  // 构建节点映射
  const nodeMap = {}
  nodesData.forEach(n => { nodeMap[n.id] = n })

  const nodes = nodesData.map(n => ({
    id: n.id,
    name: n.label || '未命名',
    type: n.metadata?.agent_type || n.node_type || 'unknown',
    rawData: n,
  }))

  const nodeIds = new Set(nodes.map(n => n.id))

  // 处理边
  const edgePairCount = {}
  const selfLoopEdges = {}
  const tempEdges = edgesData.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))

  tempEdges.forEach(e => {
    if (e.source === e.target) {
      if (!selfLoopEdges[e.source]) selfLoopEdges[e.source] = []
      selfLoopEdges[e.source].push({
        ...e,
        source_name: nodeMap[e.source]?.label,
        target_name: nodeMap[e.target]?.label,
      })
    } else {
      const pairKey = [e.source, e.target].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })

  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set()
  const edges = []

  tempEdges.forEach(e => {
    const isSelfLoop = e.source === e.target

    if (isSelfLoop) {
      if (processedSelfLoopNodes.has(e.source)) return
      processedSelfLoopNodes.add(e.source)
      const allSelfLoops = selfLoopEdges[e.source]
      const nodeName = nodeMap[e.source]?.label || '未知'
      edges.push({
        source: e.source,
        target: e.target,
        type: 'SELF_LOOP',
        name: `自关系 (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops,
        },
      })
      return
    }

    const pairKey = [e.source, e.target].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1

    const isReversed = e.source > e.target
    let curvature = 0
    if (totalCount > 1) {
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      if (isReversed) curvature = -curvature
    }

    edges.push({
      source: e.source,
      target: e.target,
      type: e.edge_type || e.relation || '关联',
      name: e.relation || e.label || e.edge_type || '关联',
      curvature,
      isSelfLoop: false,
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source]?.label,
        target_name: nodeMap[e.target]?.label,
      },
    })
  })

  // 颜色映射
  const colorMap = {}
  entityTypes.value.forEach(t => { colorMap[t.name] = t.color })
  const getColor = (type) => colorMap[type] || '#999'

  // 力导向仿真
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      const baseDistance = 150
      const edgeCount = d.pairTotal || 1
      return baseDistance + (edgeCount - 1) * 50
    }))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(50))
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))

  currentSimulation = simulation

  const g = svg.append('g')

  // 缩放
  zoomBehavior = d3.zoom()
    .extent([[0, 0], [width, height]])
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoomBehavior)

  // 曲线路径计算
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y

    if (d.isSelfLoop) {
      const loopRadius = 30
      const x1 = sx + 8
      const y1 = sy - 4
      const x2 = sx + 8
      const y2 = sy + 4
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }

    if (d.curvature === 0) {
      return `M${sx},${sy} L${tx},${ty}`
    }

    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }

  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y

    if (d.isSelfLoop) {
      return { x: sx + 70, y: sy }
    }

    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }

    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    return { x: midX, y: midY }
  }

  // 绘制边
  const linkGroup = g.append('g').attr('class', 'links')

  const link = linkGroup.selectAll('path')
    .data(edges)
    .enter().append('path')
    .attr('stroke', '#C0C0C0')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      d3.select(event.target).attr('stroke', '#3498db').attr('stroke-width', 3)

      selectedItem.value = {
        type: 'edge',
        data: d.rawData,
        sourceName: d.rawData.source_name || d.source.id,
        targetName: d.rawData.target_name || d.target.id,
        evolutionHistory: d.rawData.metadata?.evolution_history || d.rawData.evolution_history || [],
      }
    })

  // 边标签背景
  const linkLabelBg = linkGroup.selectAll('rect')
    .data(edges)
    .enter().append('rect')
    .attr('fill', 'rgba(255,255,255,0.95)')
    .attr('rx', 3)
    .attr('ry', 3)
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', 'rgba(52, 152, 219, 0.1)')

      selectedItem.value = {
        type: 'edge',
        data: d.rawData,
        sourceName: d.rawData.source_name || d.source.id,
        targetName: d.rawData.target_name || d.target.id,
        evolutionHistory: d.rawData.metadata?.evolution_history || d.rawData.evolution_history || [],
      }
    })

  // 边标签
  const linkLabels = linkGroup.selectAll('text')
    .data(edges)
    .enter().append('text')
    .text(d => d.name)
    .attr('font-size', '9px')
    .attr('fill', '#666')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', '#3498db')

      selectedItem.value = {
        type: 'edge',
        data: d.rawData,
        sourceName: d.rawData.source_name || d.source.id,
        targetName: d.rawData.target_name || d.target.id,
        evolutionHistory: d.rawData.metadata?.evolution_history || d.rawData.evolution_history || [],
      }
    })

  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  // 绘制节点
  const nodeGroup = g.append('g').attr('class', 'nodes')

  const node = nodeGroup.selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', 10)
    .attr('fill', d => getColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2.5)
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => {
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)
        if (!d._isDragging && distance > 3) {
          d._isDragging = true
          simulation.alphaTarget(0.3).restart()
        }
        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      node.attr('stroke', '#fff').attr('stroke-width', 2.5)
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      d3.select(event.target).attr('stroke', '#E91E63').attr('stroke-width', 4)
      link.filter(l => l.source.id === d.id || l.target.id === d.id)
        .attr('stroke', '#E91E63')
        .attr('stroke-width', 2.5)

      selectedItem.value = {
        type: 'node',
        data: d.rawData,
        entityType: d.type,
        color: getColor(d.type),
      }
      emit('node-click', d.rawData)
    })
    .on('mouseenter', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.id !== d.rawData.id) {
        d3.select(event.target).attr('stroke', '#333').attr('stroke-width', 3)
      }
    })
    .on('mouseleave', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.id !== d.rawData.id) {
        d3.select(event.target).attr('stroke', '#fff').attr('stroke-width', 2.5)
      }
    })

  // 节点标签
  const nodeLabels = nodeGroup.selectAll('text')
    .data(nodes)
    .enter().append('text')
    .text(d => d.name.length > 8 ? d.name.substring(0, 8) + '…' : d.name)
    .attr('font-size', '11px')
    .attr('fill', '#333')
    .attr('font-weight', '500')
    .attr('dx', 14)
    .attr('dy', 4)
    .style('pointer-events', 'none')
    .style('font-family', 'system-ui, sans-serif')

  // tick 更新
  simulation.on('tick', () => {
    link.attr('d', d => getLinkPath(d))

    linkLabels.each(function(d) {
      const mid = getLinkMidpoint(d)
      d3.select(this).attr('x', mid.x).attr('y', mid.y)
    })

    linkLabelBg.each(function(d, i) {
      const mid = getLinkMidpoint(d)
      const textEl = linkLabels.nodes()[i]
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
    })

    node.attr('cx', d => d.x).attr('cy', d => d.y)
    nodeLabels.attr('x', d => d.x).attr('y', d => d.y)
  })

  svg.on('click', () => {
    selectedItem.value = null
    node.attr('stroke', '#fff').attr('stroke-width', 2.5)
    linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
    linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
    linkLabels.attr('fill', '#666')
  })
}

watch(() => props.graphData, () => {
  nextTick(renderGraph)
}, { deep: true })

watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) linkLabelsRef.style('display', newVal ? 'block' : 'none')
  if (linkLabelBgRef) linkLabelBgRef.style('display', newVal ? 'block' : 'none')
})

const handleResize = () => {
  nextTick(renderGraph)
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #FAFAFA;
  background-image: radial-gradient(#D0D0D0 1.5px, transparent 1.5px);
  background-size: 24px 24px;
  overflow: hidden;
}

.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(255,255,255,0.95), rgba(255,255,255,0));
  pointer-events: none;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  pointer-events: auto;
}

.header-tools {
  pointer-events: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid #E0E0E0;
  background: #FFF;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  font-size: 13px;
}

.tool-btn:hover {
  background: #F5F5F5;
  color: #000;
  border-color: #CCC;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-view, .graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.2;
}

.graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(255,255,255,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  z-index: 10;
}

.legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #E91E63;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  max-width: 320px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #555;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.graph-toolbar {
  position: absolute;
  bottom: 24px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: rgba(255, 255, 255, 0.95);
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  z-index: 10;
  font-size: 12px;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-label {
  color: #666;
  font-weight: 500;
  min-width: 36px;
}

.toolbar-select {
  padding: 4px 8px;
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  background: #FFF;
  color: #333;
  font-size: 12px;
  cursor: pointer;
}

.toolbar-btn {
  padding: 4px 10px;
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  background: #FFF;
  color: #333;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: #F5F5F5;
}

.replay-slider {
  width: 100px;
  cursor: pointer;
}

.replay-label {
  min-width: 32px;
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
  color: #7B2D8E;
  font-weight: 600;
}

.edge-labels-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #FFF;
  padding: 0 12px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  cursor: pointer;
  font-size: 13px;
  color: #666;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #E0E0E0;
  border-radius: 22px;
  transition: 0.3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

input:checked + .slider {
  background-color: #7B2D8E;
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.toggle-label {
  font-size: 12px;
  color: #666;
}

/* Detail Panel */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  overflow: hidden;
  font-size: 13px;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.detail-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #FAFAFA;
  border-bottom: 1px solid #EEE;
  flex-shrink: 0;
}

.detail-title {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.detail-type-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  margin-left: auto;
  margin-right: 12px;
}

.detail-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #999;
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.detail-close:hover {
  color: #333;
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-row {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-label {
  color: #888;
  font-size: 12px;
  font-weight: 500;
  min-width: 60px;
}

.detail-value {
  color: #333;
  flex: 1;
  word-break: break-word;
}

.detail-value.uuid-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #666;
}

.detail-value.fact-text {
  line-height: 1.5;
  color: #444;
}

.detail-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #F0F0F0;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 10px;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
}

.property-key {
  color: #888;
  font-weight: 500;
  min-width: 90px;
}

.property-value {
  color: #333;
  flex: 1;
}

.edge-relation-header {
  background: #F8F8F8;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  line-height: 1.5;
  word-break: break-word;
}

.evolution-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evolution-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: #FAFAFA;
  border-radius: 6px;
  border-left: 3px solid #7B2D8E;
}

.evolution-round {
  font-size: 11px;
  font-weight: 600;
  color: #7B2D8E;
  min-width: 32px;
}

.evolution-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.evolution-relation {
  font-size: 12px;
  font-weight: 500;
  color: #333;
}

.evolution-desc {
  font-size: 11px;
  color: #666;
  line-height: 1.4;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E0E0E0;
  border-top-color: #7B2D8E;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}
</style>
