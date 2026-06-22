import axios from 'axios'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
})

service.interceptors.request.use(
  config => config,
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

service.interceptors.response.use(
  response => {
    const res = response.data
    if (!res.success && res.success !== undefined) {
      return Promise.reject(new Error(res.message || res.error || 'Error'))
    }
    return res
  },
  error => {
    console.error('Response error:', error)
    // 提取后端返回的 detail 信息作为错误消息
    const detail = error.response?.data?.detail
    const message = detail || error.message || '请求失败'
    const enhancedError = new Error(message)
    enhancedError.response = error.response
    enhancedError.status = error.response?.status
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('请求超时')
    }
    if (error.message === 'Network Error') {
      console.error('网络错误')
    }
    return Promise.reject(enhancedError)
  }
)

export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      // 推演被锁定（HTTP 423）属于业务状态，不需要重试
      if (error.status === 423 || error.response?.status === 423) {
        throw error
      }
      if (i === maxRetries - 1) throw error
      console.warn(`请求失败，重试 (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

// 健康检查
export function checkHealth() {
  return service({ url: '/health', method: 'get', baseURL: '' })
}

// 推演
export function createSimulation(data) {
  return requestWithRetry(() => service({ url: '/simulations', method: 'post', data }))
}

export function getSimulation(id) {
  return service({ url: `/simulations/${id}`, method: 'get' })
}

export function listSimulations(params = {}) {
  return service({ url: '/simulations', method: 'get', params })
}

export function deleteSimulation(id) {
  return service({ url: `/simulations/${id}`, method: 'delete' })
}

export function stepSimulation(id, data = {}) {
  return requestWithRetry(() => service({ url: `/simulations/${id}/step`, method: 'post', data }))
}

export function batchStep(id, data) {
  return requestWithRetry(() => service({ url: `/simulations/${id}/batch-step`, method: 'post', data }))
}

export function getBatchStatus(id, taskId) {
  return service({ url: `/simulations/${id}/batch-status/${taskId}`, method: 'get' })
}

export function pauseSimulation(id) {
  return service({ url: `/simulations/${id}/pause`, method: 'post' })
}

export function resumeSimulation(id) {
  return service({ url: `/simulations/${id}/resume`, method: 'post' })
}

// 事件注入
export function injectEvent(simulationId, data) {
  return requestWithRetry(() => service({ url: `/simulations/${simulationId}/events`, method: 'post', data }))
}

export function getInterventionOptions(simulationId, optionType = 'global', agentId) {
  const params = { simulation_id: simulationId, option_type: optionType }
  if (agentId) params.agent_id = agentId
  return service({ url: '/interventions/options', method: 'get', params })
}

// 已废弃：intervene / quickIntervene 不再使用（干预与推进分离）

// Agent
export function getAgentDetail(simulationId, agentId) {
  return service({ url: `/simulations/${simulationId}/agents/${agentId}`, method: 'get' })
}

export function modifyAgent(simulationId, agentId, data) {
  return service({ url: `/simulations/${simulationId}/agents/${agentId}/modify`, method: 'post', data: { simulation_id: simulationId, agent_id: agentId, ...data } })
}

export function addAgent(simulationId, data) {
  return service({ url: `/simulations/${simulationId}/agents`, method: 'post', data })
}

export function getAgentActions(simulationId, agentId) {
  return service({ url: `/simulations/${simulationId}/agents/${agentId}/actions`, method: 'get' })
}

// 新闻检索
export function searchNews(query, topk = 10) {
  return service({ url: '/news/search', method: 'post', data: { query, topk } })
}

// 报告生成
export function generateReport(simulationId) {
  return requestWithRetry(() => service({ url: `/simulations/${simulationId}/report`, method: 'post', data: {} }))
}

export function getReport(simulationId) {
  return service({ url: `/simulations/${simulationId}/report`, method: 'get' })
}

export function generateBaselineReport(simulationId) {
  return requestWithRetry(() => service({ url: `/simulations/${simulationId}/report/baseline`, method: 'post', data: {} }))
}

export default service
