<template>
  <div v-if="visible" class="agent-detail-overlay" @click.self="close">
    <div class="agent-detail-panel">
      <div class="detail-header">
        <div class="detail-title-group">
          <span class="detail-type-badge">{{ agent?.type || 'ENTITY' }}</span>
          <span class="detail-name">{{ agent?.name || '未命名' }}</span>
        </div>
        <div class="header-actions">
          <button class="edit-toggle-btn" @click="isEditing = !isEditing">
            {{ isEditing ? '完成' : '编辑' }}
          </button>
          <button class="close-btn" @click="close">×</button>
        </div>
      </div>

      <div class="detail-body">
        <!-- 基础信息 -->
        <div class="detail-section">
          <div class="section-label">基础信息</div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-key">可行动</span>
              <span v-if="!isEditing" class="info-value">{{ agent?.is_actionable ? '是' : '否' }}</span>
              <input v-else v-model="editForm.is_actionable" type="checkbox" class="edit-checkbox" />
            </div>
            <div class="info-item">
              <span class="info-key">情绪</span>
              <span v-if="!isEditing" class="info-value sentiment">{{ (agent?.sentiment ?? 0).toFixed(2) }}</span>
              <input v-else v-model.number="editForm.sentiment" type="number" min="-1" max="1" step="0.1" class="edit-input" />
            </div>
            <div class="info-item">
              <span class="info-key">行动次数</span>
              <span class="info-value">{{ agent?.action_count || 0 }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">创建回合</span>
              <span class="info-value">{{ agent?.created_round || 0 }}</span>
            </div>
          </div>
        </div>

        <!-- 描述 -->
        <div class="detail-section">
          <div class="section-label">描述</div>
          <div v-if="!isEditing" class="description-text">{{ agent?.description || '暂无描述' }}</div>
          <textarea v-else v-model="editForm.description" rows="3" class="edit-textarea"></textarea>
        </div>

        <!-- 性格 -->
        <div class="detail-section">
          <div class="section-label">性格</div>
          <div v-if="!isEditing" class="personality-text">{{ agent?.personality || '暂无' }}</div>
          <input v-else v-model="editForm.personality" class="edit-input" />
        </div>

        <!-- 目标 -->
        <div class="detail-section">
          <div class="section-label">
            目标
            <button v-if="isEditing" class="add-btn" @click="addGoal">+</button>
          </div>
          <div v-if="!isEditing" class="goals-list">
            <span v-for="(goal, idx) in agent?.goals" :key="idx" class="goal-tag">{{ goal }}</span>
            <span v-if="!agent?.goals?.length" class="empty-text">暂无目标</span>
          </div>
          <div v-else class="edit-goals-list">
            <div v-for="(goal, idx) in editForm.goals" :key="idx" class="edit-goal-item">
              <input v-model="editForm.goals[idx]" class="edit-input" />
              <button class="remove-btn" @click="removeGoal(idx)">×</button>
            </div>
          </div>
        </div>

        <!-- 属性 -->
        <div class="detail-section" v-if="agent?.attributes && Object.keys(agent.attributes).length">
          <div class="section-label">属性</div>
          <div class="properties-list">
            <div v-for="(value, key) in agent.attributes" :key="key" class="property-item">
              <span class="property-key">{{ key }}:</span>
              <span class="property-value">{{ value }}</span>
            </div>
          </div>
        </div>

        <!-- 关键词 -->
        <div class="detail-section" v-if="agent?.keywords?.length">
          <div class="section-label">关键词</div>
          <div class="keywords-list">
            <span v-for="(kw, idx) in agent.keywords" :key="idx" class="keyword-tag">{{ kw }}</span>
          </div>
        </div>

        <!-- 记忆 -->
        <div class="detail-section" v-if="agent?.memory?.short_term?.length">
          <div class="section-label">短期记忆 ({{ agent.memory.short_term.length }})</div>
          <div class="memory-list">
            <div v-for="(mem, idx) in agent.memory.short_term.slice(-5)" :key="idx" class="memory-item">
              <span class="memory-round">R{{ mem.round }}</span>
              <span class="memory-content">{{ mem.content }}</span>
            </div>
          </div>
        </div>

        <!-- 事件日志 -->
        <div class="detail-section" v-if="agent?.event_log?.length">
          <div class="section-label">
            事件日志 ({{ agent.event_log.length }})
            <button v-if="agent.event_log.length > 5" class="toggle-btn" @click="showAllLogs = !showAllLogs">
              {{ showAllLogs ? '收起' : '显示全部' }}
            </button>
          </div>
          <div class="event-log-list">
            <div v-for="(log, idx) in displayedEventLogs" :key="idx" class="event-log-item">
              <div class="event-log-header">
                <span class="event-log-round">R{{ log.round || '?' }}</span>
                <span class="event-log-action">{{ log.action || log.type || '行动' }}</span>
              </div>
              <div v-if="log.content" class="event-log-content">{{ log.content }}</div>
              <div v-if="log.reasoning" class="event-log-reasoning">{{ log.reasoning }}</div>
            </div>
          </div>
        </div>

        <!-- 关系摘要 -->
        <div class="detail-section" v-if="relationshipSummary?.length">
          <div class="section-label">关系 ({{ relationshipSummary.length }})</div>
          <div class="relation-list">
            <div v-for="(rel, idx) in relationshipSummary" :key="idx" class="relation-item">
              <span class="relation-target">{{ rel.target_name || rel.target_id }}</span>
              <span class="relation-type">{{ rel.relation }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 编辑模式保存栏 -->
      <div v-if="isEditing" class="edit-footer">
        <button class="cancel-btn" @click="cancelEdit">取消</button>
        <button class="save-btn" @click="saveEdit">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  visible: Boolean,
  agent: Object,
  relationshipSummary: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'field-change'])

const isEditing = ref(false)
const showAllLogs = ref(false)
const editForm = ref({
  sentiment: 0,
  description: '',
  personality: '',
  goals: [],
  is_actionable: true,
})

// 当 agent 变化或进入编辑模式时，同步数据
watch(() => props.agent, (agent) => {
  if (agent) {
    editForm.value = {
      sentiment: agent.sentiment ?? 0,
      description: agent.description || '',
      personality: agent.personality || '',
      goals: agent.goals ? [...agent.goals] : [],
      is_actionable: agent.is_actionable !== false,
    }
  }
}, { immediate: true })

const displayedEventLogs = computed(() => {
  if (!props.agent?.event_log) return []
  return showAllLogs.value ? props.agent.event_log : props.agent.event_log.slice(-5)
})

function close() {
  isEditing.value = false
  showAllLogs.value = false
  emit('close')
}

function addGoal() {
  editForm.value.goals.push('')
}

function removeGoal(idx) {
  editForm.value.goals.splice(idx, 1)
}

function cancelEdit() {
  isEditing.value = false
  // 重置为原始值
  if (props.agent) {
    editForm.value = {
      sentiment: props.agent.sentiment ?? 0,
      description: props.agent.description || '',
      personality: props.agent.personality || '',
      goals: props.agent.goals ? [...props.agent.goals] : [],
      is_actionable: props.agent.is_actionable !== false,
    }
  }
}

function saveEdit() {
  if (!props.agent) return
  const changes = []
  if (editForm.value.sentiment !== props.agent.sentiment) {
    changes.push({ field: 'sentiment', value: editForm.value.sentiment })
  }
  if (editForm.value.description !== props.agent.description) {
    changes.push({ field: 'description', value: editForm.value.description })
  }
  if (editForm.value.personality !== props.agent.personality) {
    changes.push({ field: 'personality', value: editForm.value.personality })
  }
  if (editForm.value.is_actionable !== props.agent.is_actionable) {
    changes.push({ field: 'is_actionable', value: !!editForm.value.is_actionable })
  }
  const originalGoals = JSON.stringify(props.agent.goals || [])
  const newGoals = JSON.stringify(editForm.value.goals)
  if (originalGoals !== newGoals) {
    changes.push({ field: 'goals', value: editForm.value.goals })
  }
  changes.forEach(c => {
    emit('field-change', { agent_id: props.agent.id, field: c.field, value: c.value })
  })
  isEditing.value = false
}
</script>

<style scoped>
.edit-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.agent-detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agent-detail-panel {
  background: #FFF;
  border-radius: 10px;
  width: 480px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #EAEAEA;
  background: #FAFAFA;
  flex-shrink: 0;
}

.detail-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-type-badge {
  font-size: 10px;
  font-weight: 700;
  color: #FFF;
  background: #000;
  padding: 3px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.detail-name {
  font-size: 16px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.edit-toggle-btn {
  background: #F5F5F5;
  border: 1px solid #E0E0E0;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.edit-toggle-btn:hover {
  background: #EAEAEA;
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

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.detail-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #F0F0F0;
}

.detail-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-key {
  font-size: 10px;
  color: #999;
}

.info-value {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.status-badge {
  display: inline-block;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.sentiment {
  font-family: 'JetBrains Mono', monospace;
}

.description-text,
.personality-text {
  font-size: 12px;
  color: #555;
  line-height: 1.6;
}

.goals-list,
.keywords-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.goal-tag,
.keyword-tag {
  font-size: 11px;
  background: #F5F5F5;
  border: 1px solid #E0E0E0;
  padding: 4px 10px;
  border-radius: 12px;
  color: #555;
}

.empty-text {
  font-size: 12px;
  color: #999;
  font-style: italic;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.property-item {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.property-key {
  color: #888;
  font-weight: 500;
  min-width: 80px;
}

.property-value {
  color: #333;
  flex: 1;
}

.memory-list,
.event-log-list,
.relation-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.memory-item,
.relation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 6px 8px;
  background: #F9F9F9;
  border-radius: 4px;
}

.event-log-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  padding: 8px;
  background: #F9F9F9;
  border-radius: 4px;
}

.event-log-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-log-content {
  color: #555;
  line-height: 1.4;
  font-size: 11px;
}

.event-log-reasoning {
  color: #888;
  font-size: 10px;
  line-height: 1.4;
  font-style: italic;
  border-left: 2px solid #DDD;
  padding-left: 8px;
}

.memory-round,
.event-log-round {
  font-size: 10px;
  font-weight: 600;
  color: #999;
  background: #E0E0E0;
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.memory-content {
  color: #555;
  line-height: 1.4;
}

.relation-target {
  font-weight: 600;
  color: #333;
}

.relation-type {
  color: #7B2D8E;
  background: #F3E5F5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  margin-left: auto;
}

/* 编辑控件 */
.edit-input,
.edit-select,
.edit-textarea {
  padding: 6px 8px;
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  background: #FAFAFA;
  width: 100%;
}

.edit-input:focus,
.edit-select:focus,
.edit-textarea:focus {
  outline: none;
  border-color: #999;
}

.edit-goals-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.edit-goal-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.add-btn {
  background: #F5F5F5;
  border: 1px solid #E0E0E0;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.add-btn:hover {
  background: #EAEAEA;
}

.toggle-btn {
  background: #F5F5F5;
  border: 1px solid #E0E0E0;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  color: #666;
}

.toggle-btn:hover {
  background: #EAEAEA;
}

.remove-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 16px;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-btn:hover {
  color: #C62828;
}

.edit-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid #EAEAEA;
  background: #FAFAFA;
  flex-shrink: 0;
}

.cancel-btn {
  padding: 8px 16px;
  border: 1px solid #E0E0E0;
  background: #FFF;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.save-btn {
  padding: 8px 16px;
  border: none;
  background: #000;
  color: #FFF;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.save-btn:hover {
  opacity: 0.85;
}
</style>
