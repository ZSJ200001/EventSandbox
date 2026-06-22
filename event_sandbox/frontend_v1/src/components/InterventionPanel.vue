<template>
  <div class="intervention-panel">
    <div class="panel-header">
      <span class="panel-title">干预操作</span>
    </div>

    <div class="intervention-types">
      <button
        v-for="t in types"
        :key="t.key"
        class="type-btn"
        :class="{ active: currentType === t.key }"
        @click="selectType(t.key)"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- 事件注入 -->
    <div v-if="currentType === 'event'" class="intervention-form">
      <div class="form-group">
        <label>事件描述</label>
        <textarea
          v-model="eventDescription"
          rows="4"
          placeholder="输入外部事件描述，例如：竞争对手突然降价20%，市场格局生变..."
        ></textarea>
      </div>
      <div class="btn-row">
        <button class="secondary-btn" :disabled="isLoading || generatingOptions" @click="loadOptions">
          <span v-if="generatingOptions" class="spinner-sm"></span>
          {{ generatingOptions ? '生成中...' : '🤖 生成建议' }}
        </button>
        <button class="secondary-btn news-btn" :disabled="isSearchingNews || !eventDescription" @click="handleSearchNews">
          <span v-if="isSearchingNews" class="spinner-sm"></span>
          {{ isSearchingNews ? '检索中...' : '🔍 检索相关新闻' }}
        </button>
      </div>
      <div v-if="optionsError" class="options-error">{{ optionsError }}</div>
      <div v-else-if="eventOptions?.length" class="options-list">
        <div class="options-group-title">建议事件</div>
        <button
          v-for="opt in eventOptions"
          :key="opt.key"
          class="option-btn"
          @click="eventDescription = opt.value || opt.label"
        >
          {{ opt.label }}
        </button>
      </div>
      <!-- 新闻检索结果 -->
      <div v-if="newsResults.length" class="news-results">
        <div class="options-group-title">相关新闻（点击填入）</div>
        <div
          v-for="(news, idx) in newsResults"
          :key="idx"
          class="news-card"
          @click="eventDescription = news.description || news.title"
        >
          <div class="news-title">{{ news.title }}</div>
          <div class="news-meta">
            <span v-if="news.time" class="news-time">{{ news.time }}</span>
            <span v-if="news.keywords" class="news-keywords">{{ news.keywords }}</span>
          </div>
          <div v-if="news.description" class="news-desc">{{ news.description }}</div>
        </div>
      </div>
      <button class="action-btn" :disabled="!eventDescription || isLoading" @click="submitEvent">
        <span v-if="isLoading" class="spinner-sm"></span>
        {{ isLoading ? '处理中...' : '注入事件' }}
      </button>
    </div>

    <!-- 添加实体 -->
    <div v-else-if="currentType === 'add_agent'" class="intervention-form">
      <div class="form-group">
        <label>实体名称</label>
        <input type="text" v-model="newAgentName" placeholder="输入实体名称..." />
      </div>
      <div class="form-group">
        <label>实体类型</label>
        <select v-model="newAgentType">
          <option value="individual">个人</option>
          <option value="company">企业</option>
          <option value="government">政府</option>
          <option value="organization">组织</option>
          <option value="location">地点</option>
          <option value="military">军事单位</option>
          <option value="vehicle">载具/设备</option>
        </select>
      </div>
      <div class="form-group">
        <label>描述</label>
        <textarea v-model="newAgentDesc" rows="2" placeholder="输入描述..."></textarea>
      </div>
      <button class="action-btn" :disabled="!newAgentName || isLoading" @click="submitAddAgent">
        <span v-if="isLoading" class="spinner-sm"></span>
        {{ isLoading ? '处理中...' : '添加实体' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { searchNews } from '@/api'

const props = defineProps({
  isLoading: Boolean,
  generatingOptions: Boolean,
  eventOptions: Array,
  optionsError: String,
})

const emit = defineEmits([
  'inject-event',
  'add-agent',
  'load-options',
])

const types = [
  { key: 'event', label: '事件注入' },
  { key: 'add_agent', label: '添加实体' },
]

const currentType = ref('event')

// 表单数据
const eventDescription = ref('')
const newAgentName = ref('')
const newAgentType = ref('individual')
const newAgentDesc = ref('')

// 新闻检索
const isSearchingNews = ref(false)
const newsResults = ref([])

function selectType(type) {
  currentType.value = type
}

function submitEvent() {
  if (!eventDescription.value.trim()) return
  emit('inject-event', { description: eventDescription.value.trim() })
  eventDescription.value = ''
  newsResults.value = []
}

function submitAddAgent() {
  emit('add-agent', {
    name: newAgentName.value,
    type: newAgentType.value,
    description: newAgentDesc.value,
  })
  newAgentName.value = ''
  newAgentDesc.value = ''
}

function loadOptions() {
  emit('load-options')
}

async function handleSearchNews() {
  if (!eventDescription.value.trim()) return
  isSearchingNews.value = true
  newsResults.value = []
  try {
    const res = await searchNews(eventDescription.value.trim(), 10)
    if (res.results && res.results.length) {
      newsResults.value = res.results
    } else {
      newsResults.value = []
    }
  } catch (e) {
    console.error('新闻检索失败:', e)
    newsResults.value = []
  } finally {
    isSearchingNews.value = false
  }
}
</script>

<style scoped>
.intervention-panel {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 16px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.intervention-types {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 12px 0;
}

.type-btn {
  border: 1px solid #E0E0E0;
  background: #FFF;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.type-btn:hover {
  background: #F5F5F5;
}

.type-btn.active {
  background: #000;
  color: #FFF;
  border-color: #000;
}

.intervention-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group label {
  font-size: 12px;
  font-weight: 500;
  color: #666;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 8px 10px;
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  background: #FAFAFA;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #999;
}

.action-btn {
  width: 100%;
  background: #000;
  color: #FFF;
  border: none;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.action-btn:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn:disabled {
  background: #CCC;
  cursor: not-allowed;
}

.secondary-btn {
  width: 100%;
  background: #F5F5F5;
  color: #333;
  border: 1px solid #E0E0E0;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.secondary-btn:hover:not(:disabled) {
  background: #EAEAEA;
}

.options-error {
  margin-top: 4px;
  padding: 8px 10px;
  background: #FDECEA;
  border: 1px solid #F5C6CB;
  border-radius: 4px;
  color: #C0392B;
  font-size: 12px;
  line-height: 1.5;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.options-group-title {
  font-size: 10px;
  color: #999;
  font-weight: 600;
  text-transform: uppercase;
  margin-top: 4px;
}

.option-btn {
  background: #F5F5F5;
  border: 1px solid #EAEAEA;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.option-btn:hover {
  background: #EAEAEA;
}

.btn-row {
  display: flex;
  gap: 8px;
}

.btn-row .secondary-btn {
  flex: 1;
}

.news-btn {
  background: #FFF3E0;
  border-color: #FFCC80;
  color: #E65100;
}

.news-btn:hover:not(:disabled) {
  background: #FFE0B2;
}

.news-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.news-card {
  background: #FAFAFA;
  border: 1px solid #EAEAEA;
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.news-card:hover {
  background: #F0F0F0;
  border-color: #CCC;
}

.news-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  line-height: 1.4;
  margin-bottom: 4px;
}

.news-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.news-time {
  font-size: 11px;
  color: #999;
}

.news-keywords {
  font-size: 11px;
  color: #1976D2;
  background: #E3F2FD;
  padding: 1px 6px;
  border-radius: 3px;
}

.news-desc {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid #FFCCBC;
  border-top-color: #FF5722;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
