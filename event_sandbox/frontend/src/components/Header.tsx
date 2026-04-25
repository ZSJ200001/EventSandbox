import { useSimulationStore } from '../stores/simulationStore'

export default function Header() {
  const { simulation } = useSimulationStore()

  return (
    <header className="app-header">
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <h1>EventSandbox</h1>
        <span className="subtitle">智能事件推演沙盘</span>
      </div>
      {simulation && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span>推演: {simulation.name}</span>
          <span style={{
            padding: '4px 12px',
            background: 'rgba(255,255,255,0.2)',
            borderRadius: '12px',
            fontSize: '13px'
          }}>
            回合: {simulation.current_round} / {simulation.rounds}
          </span>
          <span style={{
            padding: '4px 12px',
            background: simulation.status === 'running' ? '#38ef7d' : '#f45c43',
            borderRadius: '12px',
            fontSize: '13px',
            color: simulation.status === 'running' ? '#333' : 'white'
          }}>
            {simulation.status === 'running' ? '运行中' :
             simulation.status === 'completed' ? '已完成' :
             simulation.status === 'paused' ? '已暂停' : '待启动'}
          </span>
        </div>
      )}
    </header>
  )
}
