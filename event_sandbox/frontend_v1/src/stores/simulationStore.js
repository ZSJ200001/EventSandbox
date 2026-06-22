import { reactive, readonly } from 'vue'
import * as api from '@/api'

function createLog(msg) {
  const now = new Date()
  const time = now.toLocaleTimeString('zh-CN', { hour12: false }) + '.' + now.getMilliseconds().toString().padStart(3, '0')
  return { time, msg }
}

const state = reactive({
  // 推演数据
  simulation: null,
  agents: [],
  topology: null,
  recentEvents: [],

  // UI 状态
  isLoading: false,
  isRunning: false,
  error: null,
  logs: [],

  // 干预状态
  generatedEventOptions: null,
  generatingOptions: false,
  optionsError: null,

  // 报告
  report: null,
  baselineReport: null,
  isGeneratingReport: false,
  isGeneratingBaselineReport: false,

  // 批量
  batchSteps: 5,

  // 系统状态
  backendHealthy: false,
  llmConnected: false,
})

function addLog(msg) {
  state.logs.push(createLog(msg))
  if (state.logs.length > 200) state.logs.shift()
}

function clearError() {
  state.error = null
}

function setError(msg) {
  state.error = msg
  addLog(`错误: ${msg}`)
}

async function checkHealth() {
  try {
    const data = await api.checkHealth()
    state.backendHealthy = data.status === 'healthy'
    state.llmConnected = data.llm_connected
    addLog(`后端状态: ${data.status}, LLM: ${data.llm_connected ? '已连接' : '未连接'}`)
    return data
  } catch (err) {
    state.backendHealthy = false
    state.llmConnected = false
    addLog(`后端连接失败: ${err.message}`)
    return null
  }
}

async function createSimulation(name, description, eventText, rounds = 10, config) {
  state.isLoading = true
  clearError()
  addLog(`开始创建推演: ${name}`)
  try {
    const data = await api.createSimulation({ name, description, event_text: eventText, rounds, config })
    state.simulation = data.simulation
    state.agents = data.generated_agents || []
    state.topology = data.topology
    state.recentEvents = []
    addLog(`推演创建成功: ${data.simulation.id}, 生成 ${data.generated_agents?.length || 0} 个实体`)
    return data
  } catch (err) {
    setError(err.message || '创建推演失败')
    throw err
  } finally {
    state.isLoading = false
  }
}

async function getSimulationState(id) {
  state.isLoading = true
  clearError()
  try {
    const data = await api.getSimulation(id)
    state.simulation = data.simulation
    state.agents = data.simulation.agents || []
    state.topology = data.simulation.topology
    state.recentEvents = data.recent_events || data.simulation.events?.slice(-10) || []
    state.isRunning = data.simulation.status === 'running'
    // 切换推演时清空旧报告，避免报告状态污染
    state.report = null
    state.baselineReport = null
    addLog(`加载推演状态: ${data.simulation.name}, 回合 ${data.simulation.current_round}/${data.simulation.rounds}`)
    return data
  } catch (err) {
    setError(err.message || '加载推演失败')
    throw err
  } finally {
    state.isLoading = false
  }
}

async function stepSimulation() {
  if (!state.simulation) return
  state.isLoading = true
  state.isRunning = true
  clearError()
  addLog(`执行回合 ${state.simulation.current_round + 1}...`)
  try {
    const data = await api.stepSimulation(state.simulation.id, { simulation_id: state.simulation.id })
    state.simulation = data.simulation
    state.agents = data.simulation.agents || []
    state.topology = data.simulation.topology
    state.recentEvents = data.new_events || []
    state.isRunning = data.simulation.status === 'running'
    addLog(`回合 ${data.simulation.current_round} 完成, 行动数: ${data.action_results?.length || 0}`)
    return data
  } catch (err) {
    setError(err.message || '执行回合失败')
    state.isRunning = false
    throw err
  } finally {
    state.isLoading = false
  }
}

async function injectEvent(description) {
  if (!state.simulation) return
  state.isLoading = true
  clearError()
  addLog(`注入事件: ${description.slice(0, 30)}...`)
  try {
    const data = await api.injectEvent(state.simulation.id, { description })
    state.simulation = data.simulation
    state.agents = data.simulation.agents || []
    state.topology = data.simulation.topology
    state.recentEvents = data.simulation.events?.slice(-10) || []
    addLog(`事件已注入, 影响实体: ${data.affected_agent_count || 0}`)
    return data
  } catch (err) {
    setError(err.message || '事件注入失败')
    throw err
  } finally {
    state.isLoading = false
  }
}

async function batchStep(steps) {
  if (!state.simulation) return
  state.isLoading = true
  state.isRunning = true
  clearError()
  const stepsToRun = steps || state.batchSteps
  addLog(`开始批量推演 ${stepsToRun} 回合...`)

  let taskId = null
  try {
    const startData = await api.batchStep(state.simulation.id, {
      simulation_id: state.simulation.id,
      steps: stepsToRun,
    })
    taskId = startData.task_id
    addLog(`批量推演任务已启动: ${taskId}`)
  } catch (err) {
    setError(`${err.message || '批量推演启动失败'}，请刷新查看最新状态`)
    state.isRunning = false
    state.isLoading = false
    throw err
  }

  // 轮询任务状态
  const maxPolls = 600
  const pollInterval = 1000
  let lastStepsExecuted = 0
  const simulationId = state.simulation.id

  try {
    for (let i = 0; i < maxPolls; i++) {
      // 用户切换了推演，停止轮询
      if (!state.simulation || state.simulation.id !== simulationId) {
        addLog('已切换推演，停止批量推演进度轮询')
        return null
      }

      await new Promise(resolve => setTimeout(resolve, pollInterval))
      const status = await api.getBatchStatus(simulationId, taskId)

      if (status.steps_executed > lastStepsExecuted) {
        lastStepsExecuted = status.steps_executed
        addLog(`批量推演进度: 已完成 ${status.steps_executed}/${status.steps_requested} 回合`)
      }

      if (status.status === 'completed') {
        await _refreshSimulation(simulationId)
        addLog(`批量推演完成: 执行 ${status.steps_executed} 回合, 原因: ${status.stop_reason || '正常结束'}`)
        return status
      }

      if (status.status === 'failed') {
        await _refreshSimulation(simulationId)
        setError(`批量推演失败: ${status.error || '未知错误'}，当前状态已同步，请确认`)
        state.isRunning = state.simulation?.status === 'running'
        throw new Error(status.error || '批量推演失败')
      }
    }

    // 轮询超时
    await _refreshSimulation(simulationId)
    setError('批量推演轮询超时，任务可能仍在后台执行，请稍后刷新查看最新状态')
    state.isRunning = state.simulation?.status === 'running'
    throw new Error('批量推演轮询超时')
  } catch (err) {
    if (!state.error) {
      setError(`${err.message || '批量推演异常'}，请刷新查看最新状态`)
    }
    state.isRunning = false
    throw err
  } finally {
    state.isLoading = false
  }
}

async function _refreshSimulation(simulationId) {
  try {
    const data = await api.getSimulation(simulationId)
    if (!state.simulation || state.simulation.id !== simulationId) return
    state.simulation = data.simulation
    state.agents = data.simulation.agents || []
    state.topology = data.simulation.topology
    state.recentEvents = data.recent_events || data.simulation.events?.slice(-10) || []
    state.isRunning = data.simulation.status === 'running'
  } catch (err) {
    addLog(`同步推演状态失败: ${err.message}`)
  }
}

async function pauseSimulation() {
  if (!state.simulation) return
  try {
    const data = await api.pauseSimulation(state.simulation.id)
    state.simulation = data.simulation
    state.isRunning = false
    addLog('推演已暂停')
  } catch (err) {
    setError(err.message)
  }
}

async function resumeSimulation() {
  if (!state.simulation) return
  try {
    const data = await api.resumeSimulation(state.simulation.id)
    state.simulation = data.simulation
    state.isRunning = true
    addLog('推演已恢复')
  } catch (err) {
    setError(err.message)
  }
}

async function deleteSimulation(id) {
  try {
    await api.deleteSimulation(id)
    addLog(`推演已删除: ${id}`)
    if (state.simulation?.id === id) {
      reset()
    }
  } catch (err) {
    setError(err.message)
  }
}

async function loadGlobalInterventionOptions() {
  if (!state.simulation) return
  state.generatingOptions = true
  state.optionsError = null
  try {
    const data = await api.getInterventionOptions(state.simulation.id, 'global')
    state.generatedEventOptions = data.event_options || []
    state.generatedEnvOptions = data.env_options || []
  } catch (err) {
    state.generatedEventOptions = []
    state.optionsError = err.message || '干预建议生成失败，请稍后重试或手动输入'
  } finally {
    state.generatingOptions = false
  }
}

async function fetchAgentDetail(agentId) {
  if (!state.simulation) return null
  try {
    return await api.getAgentDetail(state.simulation.id, agentId)
  } catch (err) {
    setError(err.message)
    return null
  }
}

async function addAgent(data) {
  if (!state.simulation) return
  state.isLoading = true
  clearError()
  try {
    const res = await api.addAgent(state.simulation.id, data)
    state.simulation = res.simulation
    state.agents = res.simulation.agents || []
    state.topology = res.simulation.topology
    addLog(`新实体已添加: ${res.agent.name}`)
    return res
  } catch (err) {
    setError(err.message)
    throw err
  } finally {
    state.isLoading = false
  }
}

async function generateReport() {
  if (!state.simulation) return
  state.isGeneratingReport = true
  clearError()
  addLog('开始生成推演报告...')
  try {
    const data = await api.generateReport(state.simulation.id)
    state.report = data
    addLog(`报告生成完成: ${data.title}`)
    return data
  } catch (err) {
    setError(err.message || '报告生成失败')
    throw err
  } finally {
    state.isGeneratingReport = false
  }
}

async function generateBaselineReport() {
  if (!state.simulation) return
  state.isGeneratingBaselineReport = true
  clearError()
  addLog('开始生成基线报告...')
  try {
    const data = await api.generateBaselineReport(state.simulation.id)
    state.baselineReport = data
    addLog(`基线报告生成完成: ${data.title}`)
    return data
  } catch (err) {
    setError(err.message || '基线报告生成失败')
    throw err
  } finally {
    state.isGeneratingBaselineReport = false
  }
}

async function getReport() {
  if (!state.simulation) return null
  try {
    const data = await api.getReport(state.simulation.id)
    state.report = data.report || null
    state.baselineReport = data.baseline_report || null
    const loaded = data.report || data.baseline_report
    if (loaded) {
      addLog(`已加载报告: ${loaded.title || '推演分析报告'}`)
    }
    return data
  } catch (err) {
    // 404 表示尚未生成，静默处理
    if (err.response?.status === 404) {
      state.report = null
      state.baselineReport = null
      return null
    }
    setError(err.message || '加载报告失败')
    return null
  }
}

function setBatchSteps(steps) {
  state.batchSteps = steps
}

function reset() {
  state.simulation = null
  state.agents = []
  state.topology = null
  state.recentEvents = []
  state.isLoading = false
  state.isRunning = false
  state.error = null
  state.logs = []
  state.generatedEventOptions = null
  state.generatingOptions = false
  state.optionsError = null
  state.report = null
  state.baselineReport = null
  state.isGeneratingReport = false
  state.isGeneratingBaselineReport = false
  state.batchSteps = 5
}

export default {
  state: readonly(state),
  addLog,
  clearError,
  setError,
  checkHealth,
  createSimulation,
  getSimulationState,
  stepSimulation,
  injectEvent,
  batchStep,
  pauseSimulation,
  resumeSimulation,
  deleteSimulation,
  loadGlobalInterventionOptions,
  fetchAgentDetail,
  addAgent,
  generateReport,
  generateBaselineReport,
  getReport,
  setBatchSteps,
  reset,
}
