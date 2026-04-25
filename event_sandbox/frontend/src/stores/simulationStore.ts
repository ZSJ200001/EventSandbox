import { create } from 'zustand'
import type {
  Simulation,
  Agent,
  Event,
  Topology,
  SimulationMetrics,
  Intervention,
  SimulationConfig,
} from '../types'

const API_BASE = '/api'

interface SimulationState {
  // Current simulation
  simulation: Simulation | null
  agents: Agent[]
  topology: Topology | null
  recentEvents: Event[]
  agentStates: Record<string, any>

  // UI state
  isLoading: boolean
  isRunning: boolean
  error: string | null

  // Intervention state
  interventionType: 'global_param' | 'agent_state' | 'external_event'
  selectedAgentId: string | null
  interventionValue: string

  // Comparison state
  comparisonResult: any | null

  // Actions
  createSimulation: (
    name: string,
    description: string,
    eventText: string,
    config?: Partial<SimulationConfig>
  ) => Promise<void>
  stepSimulation: (intervention?: Intervention) => Promise<void>
  intervene: (intervention: Intervention) => Promise<void>
  getSimulationState: (id: string) => Promise<void>
  compareScenarios: (
    simulationId: string,
    interventionType: string,
    target?: string,
    parameter?: string,
    value?: string
  ) => Promise<void>

  // UI Actions
  setInterventionType: (type: 'global_param' | 'agent_state' | 'external_event') => void
  setSelectedAgentId: (id: string | null) => void
  setInterventionValue: (value: string) => void
  setError: (error: string | null) => void
  reset: () => void
}

const initialState = {
  simulation: null,
  agents: [],
  topology: null,
  recentEvents: [],
  agentStates: {},
  isLoading: false,
  isRunning: false,
  error: null,
  interventionType: 'external_event' as const,
  selectedAgentId: null,
  interventionValue: '',
  comparisonResult: null,
}

export const useSimulationStore = create<SimulationState>((set, get) => ({
  ...initialState,

  createSimulation: async (name, description, eventText, config) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/simulations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, event_text: eventText, config }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      set({
        simulation: data.simulation,
        agents: data.generated_agents,
        topology: data.topology,
        recentEvents: [],
        agentStates: {},
        isLoading: false,
      })
    } catch (error: any) {
      set({ error: error.message, isLoading: false })
      throw error
    }
  },

  stepSimulation: async (intervention) => {
    const { simulation } = get()
    if (!simulation) return

    set({ isLoading: true, isRunning: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/simulations/${simulation.id}/step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          simulation_id: simulation.id,
          intervention,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      set({
        simulation: data.simulation,
        agents: data.simulation.agents,
        recentEvents: data.simulation.events.slice(-10),
        agentStates: {},
        isLoading: false,
        isRunning: data.simulation.status === 'running',
      })
    } catch (error: any) {
      set({ error: error.message, isLoading: false, isRunning: false })
      throw error
    }
  },

  intervene: async (intervention) => {
    const { simulation } = get()
    if (!simulation) return

    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/simulations/${simulation.id}/intervene`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          simulation_id: simulation.id,
          intervention,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      if (data.success) {
        // Refresh simulation state
        await get().getSimulationState(simulation.id)
      } else {
        set({ error: data.message, isLoading: false })
      }
    } catch (error: any) {
      set({ error: error.message, isLoading: false })
      throw error
    }
  },

  getSimulationState: async (id) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/simulations/${id}`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      set({
        simulation: data.simulation,
        agents: data.simulation.agents,
        topology: data.simulation.topology,
        recentEvents: data.recent_events,
        agentStates: data.agent_states,
        isLoading: false,
        isRunning: data.simulation.status === 'running',
      })
    } catch (error: any) {
      set({ error: error.message, isLoading: false })
      throw error
    }
  },

  compareScenarios: async (simulationId, interventionType, target, parameter, value) => {
    set({ isLoading: true, error: null })
    try {
      const params = new URLSearchParams({ intervention_type: interventionType })
      if (target) params.append('target', target)
      if (parameter) params.append('parameter', parameter)
      if (value) params.append('value', value)

      const response = await fetch(
        `${API_BASE}/simulations/${simulationId}/compare?${params}`
      )
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      set({ comparisonResult: data, isLoading: false })
    } catch (error: any) {
      set({ error: error.message, isLoading: false })
      throw error
    }
  },

  setInterventionType: (type) => set({ interventionType: type }),
  setSelectedAgentId: (id) => set({ selectedAgentId: id }),
  setInterventionValue: (value) => set({ interventionValue: value }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}))
