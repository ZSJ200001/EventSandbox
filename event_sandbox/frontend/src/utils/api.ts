const API_BASE = '/api'

export async function checkHealth(): Promise<{ status: string; llm_connected: boolean }> {
  const response = await fetch(`${API_BASE}/../health`)
  return response.json()
}

export async function createSimulation(data: {
  name: string
  description: string
  event_text: string
  config?: any
}) {
  const response = await fetch(`${API_BASE}/simulations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

export async function getSimulation(id: string) {
  const response = await fetch(`${API_BASE}/simulations/${id}`)
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

export async function stepSimulation(id: string, intervention?: any) {
  const response = await fetch(`${API_BASE}/simulations/${id}/step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ simulation_id: id, intervention }),
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

export async function intervene(id: string, intervention: any) {
  const response = await fetch(`${API_BASE}/simulations/${id}/intervene`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ simulation_id: id, intervention }),
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

export async function compareScenarios(
  id: string,
  interventionType: string,
  target?: string,
  parameter?: string,
  value?: string
) {
  const params = new URLSearchParams({ intervention_type: interventionType })
  if (target) params.append('target', target)
  if (parameter) params.append('parameter', parameter)
  if (value) params.append('value', value)

  const response = await fetch(
    `${API_BASE}/simulations/${id}/compare?${params}`
  )
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}
