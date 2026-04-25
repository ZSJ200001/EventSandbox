import { useState } from 'react'
import { Input, Button, Select } from 'antd'
import { useSimulationStore } from '../stores/simulationStore'
import type { Intervention, InterventionType } from '../types'

export default function RightSidebar() {
  const {
    simulation,
    agents,
    intervene,
    compareScenarios,
    comparisonResult,
  } = useSimulationStore()

  const [interventionType, setInterventionType] = useState<'global_param' | 'agent_state' | 'external_event'>('external_event')
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [parameter, setParameter] = useState('sentiment')
  const [value, setValue] = useState('')

  const handleIntervene = async () => {
    if (!simulation) return

    const intervention: Intervention = {
      id: `int_${Date.now()}`,
      type: interventionType as InterventionType,
      target: interventionType === 'agent_state' ? selectedAgentId : undefined,
      parameter: interventionType === 'agent_state' ? parameter : undefined,
      value: interventionType === 'external_event' ? value : parseFloat(value) || value,
      timestamp: Date.now(),
      round: simulation.current_round,
    }

    try {
      await intervene(intervention)
      setValue('')
    } catch (e) {
      console.error('干预失败:', e)
    }
  }

  const handleCompare = async () => {
    if (!simulation) return
    try {
      await compareScenarios(
        simulation.id,
        interventionType,
        selectedAgentId || undefined,
        interventionType === 'agent_state' ? parameter : undefined,
        value || undefined
      )
    } catch (e) {
      console.error('对比失败:', e)
    }
  }

  if (!simulation) {
    return (
      <aside className="panel right-sidebar">
        <div className="panel-header">Agent & 干预控制</div>
        <div className="panel-content">
          <div className="empty-state">
            <div>创建推演场景后即可管理Agent和干预</div>
          </div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="panel right-sidebar">
      <div className="panel-header">
        <span>Agent & 干预控制</span>
      </div>
      <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Agent List */}
        <div>
          <h4 style={{ fontSize: '13px', color: '#666', marginBottom: '8px' }}>
            智能体列表 ({agents.length})
          </h4>
          <div className="agent-list" style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {agents.map(agent => {
              const sentimentBelief = agent.beliefs?.find(b => b.key === 'sentiment')
              const sentiment = sentimentBelief ? Number(sentimentBelief.value) : 0

              return (
                <div
                  key={agent.id}
                  className="agent-card"
                  onClick={() => setSelectedAgentId(agent.id)}
                  style={{
                    borderColor: selectedAgentId === agent.id ? '#667eea' : undefined,
                    background: selectedAgentId === agent.id ? '#f9f9ff' : undefined,
                  }}
                >
                  <div className="agent-card-header">
                    <span className="agent-name">{agent.name}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="agent-type">{agent.type}</span>
                      <span className={`agent-status ${agent.status}`} />
                    </div>
                  </div>
                  <div className="agent-sentiment">
                    情绪: {sentiment >= 0 ? '+' : ''}{(sentiment * 100).toFixed(1)}%
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Intervention Controls */}
        <div className="intervention-form">
          <h4 style={{ fontSize: '13px', color: '#666', marginBottom: '8px' }}>
            干预控制
          </h4>

          <div className="intervention-type">
            <button
              className={interventionType === 'global_param' ? 'active' : ''}
              onClick={() => setInterventionType('global_param')}
            >
              全局参数
            </button>
            <button
              className={interventionType === 'agent_state' ? 'active' : ''}
              onClick={() => setInterventionType('agent_state')}
            >
              Agent状态
            </button>
            <button
              className={interventionType === 'external_event' ? 'active' : ''}
              onClick={() => setInterventionType('external_event')}
            >
              外部事件
            </button>
          </div>

          {interventionType === 'agent_state' && (
            <div className="input-group">
              <label>选择Agent</label>
              <Select
                value={selectedAgentId}
                onChange={setSelectedAgentId}
                placeholder="选择要干预的Agent"
                style={{ width: '100%' }}
                options={agents.map(a => ({ value: a.id, label: a.name }))}
              />
            </div>
          )}

          {interventionType === 'agent_state' && (
            <div className="input-group">
              <label>参数</label>
              <Select
                value={parameter}
                onChange={setParameter}
                style={{ width: '100%' }}
                options={[
                  { value: 'sentiment', label: '情绪值' },
                  { value: 'belief', label: '添加信念' },
                ]}
              />
            </div>
          )}

          <div className="input-group">
            <label>
              {interventionType === 'external_event' ? '事件描述' : '数值'}
            </label>
            {interventionType === 'external_event' ? (
              <Input.TextArea
                value={value}
                onChange={e => setValue(e.target.value)}
                placeholder={
                  selectedAgentId
                    ? `描述要注入到 ${agents.find(a => a.id === selectedAgentId)?.name} 的事件`
                    : '描述要注入的外部事件'
                }
                rows={2}
              />
            ) : (
              <Input
                type="number"
                value={value}
                onChange={e => setValue(e.target.value)}
                placeholder="输入数值 (-1 到 1)"
                step="0.1"
                min="-1"
                max="1"
              />
            )}
          </div>

          <div className="controls">
            <Button
              type="primary"
              onClick={handleIntervene}
              disabled={!value.trim()}
              style={{ flex: 1 }}
            >
              注入干预
            </Button>
            <Button onClick={handleCompare}>
              对比分析
            </Button>
          </div>
        </div>

        {/* Comparison Results */}
        {comparisonResult && (
          <div>
            <h4 style={{ fontSize: '13px', color: '#666', marginBottom: '8px' }}>
              对比分析报告
            </h4>
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>指标</th>
                  <th>无干预</th>
                  <th>有干预</th>
                  <th>变化</th>
                </tr>
              </thead>
              <tbody>
                {comparisonResult.comparison?.map((item: any) => (
                  <tr key={item.metric}>
                    <td>{item.metric}</td>
                    <td>{item.difference < 0 ?
                      comparisonResult.without_intervention[item.metric]?.toFixed(3) :
                      comparisonResult.with_intervention[item.metric]?.toFixed(3)
                    }</td>
                    <td>{item.difference >= 0 ?
                      comparisonResult.with_intervention[item.metric]?.toFixed(3) :
                      comparisonResult.without_intervention[item.metric]?.toFixed(3)
                    }</td>
                    <td className={item.difference >= 0 ? 'positive' : 'negative'}>
                      {item.difference >= 0 ? '+' : ''}{(item.percentage_change || 0).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </aside>
  )
}
