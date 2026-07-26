<template>
  <div class="action-timeline">
    <div class="timeline-header">
      <span class="timeline-title">推演时间轴</span>
      <div class="header-right">
        <select v-model="selectedActor" class="actor-filter">
          <option value="">全部 Agent</option>
          <option v-for="actor in uniqueActors" :key="actor" :value="actor">{{ actor }}</option>
        </select>
        <span class="timeline-count" v-if="filteredTimeline?.length">{{ filteredTimeline.length }} 条</span>
      </div>
    </div>
    <div class="timeline-content" v-if="filteredTimeline?.length">
      <div
        v-for="(entry, idx) in filteredTimeline"
        :key="idx"
        class="timeline-item"
      >
        <div class="timeline-marker" :class="entry.type"></div>
        <div class="timeline-card" :class="entry.type">
          <div class="timeline-card-header">
            <span class="actor-name">{{ entry.actor || '系统' }}</span>
            <div class="header-tags">
              <span class="round-badge">R{{ entry.round }}</span>
              <span class="action-type">{{ entry.action || entry.type }}</span>
            </div>
          </div>
          <div class="timeline-card-body">
            <p class="action-desc">{{ entry.description || '无描述' }}</p>
            <div class="action-meta" v-if="entry.details?.sentiment_change">
              情绪变化: <span :class="entry.details.sentiment_change > 0 ? 'positive' : 'negative'">{{ entry.details.sentiment_change > 0 ? '+' : '' }}{{ entry.details.sentiment_change.toFixed(2) }}</span>
            </div>
            <div class="relation-updates" v-if="entry.details?.relation_changes?.length">
              <div class="relation-tag" v-for="(rel, rIdx) in entry.details.relation_changes" :key="rIdx">
                {{ rel.source_relation || rel.relation || '关系更新' }}
              </div>
            </div>
            <div class="event-metadata" v-if="entry.type === 'world_event' && entry.details?.metadata">
              <span class="meta-tag" v-for="(value, key) in entry.details.metadata" :key="key">
                {{ key }}: {{ value }}
              </span>
            </div>
            <div class="before-after" v-if="entry.before && entry.after">
              <span class="ba-label">关系变化</span>
              <span class="ba-old">{{ entry.before.relation || '?' }}</span>
              <span class="ba-arrow">→</span>
              <span class="ba-new">{{ entry.after.relation || '?' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="timeline-empty">暂无推演记录</div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  timeline: { type: Array, default: () => [] },
})

const selectedActor = ref('')

const uniqueActors = computed(() => {
  const actors = new Set()
  props.timeline.forEach(e => {
    if (e.actor) actors.add(e.actor)
  })
  return Array.from(actors).sort()
})

const filteredTimeline = computed(() => {
  if (!selectedActor.value) return props.timeline
  return props.timeline.filter(e => e.actor === selectedActor.value)
})
</script>

<style scoped>
.action-timeline {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 16px;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.actor-filter {
  font-size: 12px;
  padding: 4px 8px;
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  background: #FFF;
  color: #333;
  outline: none;
}

.actor-filter:focus {
  border-color: #1A936F;
}

.timeline-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.timeline-count {
  font-size: 11px;
  color: #999;
  font-family: 'JetBrains Mono', monospace;
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 400px;
  overflow-y: auto;
}

.timeline-item {
  display: flex;
  gap: 12px;
  position: relative;
  padding-bottom: 16px;
}

.timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 12px;
  bottom: 0;
  width: 2px;
  background: #EAEAEA;
}

.timeline-marker {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #E91E63;
  border: 2px solid #FFF;
  box-shadow: 0 0 0 2px #E91E63;
  flex-shrink: 0;
  margin-top: 4px;
  z-index: 1;
}

.timeline-card {
  flex: 1;
  background: #FAFAFA;
  border: 1px solid #F0F0F0;
  border-radius: 6px;
  padding: 10px 12px;
}

.timeline-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.header-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.round-badge {
  font-size: 10px;
  font-weight: 700;
  color: #FFF;
  background: #333;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.action-type {
  font-size: 10px;
  color: #999;
  background: #F0F0F0;
  padding: 2px 6px;
  border-radius: 4px;
}

.timeline-card-body {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
}

.action-desc {
  margin: 0 0 6px 0;
}

.action-meta {
  font-size: 11px;
  color: #888;
  margin-bottom: 4px;
}

.action-meta .positive { color: #27ae60; font-weight: 600; }
.action-meta .negative { color: #e74c3c; font-weight: 600; }

.relation-updates {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.relation-tag {
  font-size: 10px;
  color: #7B2D8E;
  background: #F3E5F5;
  padding: 2px 6px;
  border-radius: 4px;
}

.event-metadata {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.meta-tag {
  font-size: 10px;
  color: #7B2D8E;
  background: #F3E5F5;
  padding: 2px 6px;
  border-radius: 4px;
}

/* 不同类型的时间轴条目颜色 */
.timeline-marker.external_event {
  background: #FF9800;
  box-shadow: 0 0 0 2px #FF9800;
}
.timeline-marker.agent_added {
  background: #4CAF50;
  box-shadow: 0 0 0 2px #4CAF50;
}
.timeline-marker.world_event {
  background: #9C27B0;
  box-shadow: 0 0 0 2px #9C27B0;
}

.timeline-card.external_event {
  border-left: 3px solid #FF9800;
}
.timeline-card.agent_added {
  border-left: 3px solid #4CAF50;
}
.timeline-card.world_event {
  border-left: 3px solid #9C27B0;
}

.actor-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.before-after {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
}

.ba-label {
  color: #999;
}

.ba-old {
  color: #999;
}

.ba-arrow {
  color: #999;
}

.ba-new {
  color: #e74c3c;
  font-weight: 600;
}

.timeline-empty {
  font-size: 12px;
  color: #999;
  text-align: center;
  padding: 20px 0;
}
</style>
