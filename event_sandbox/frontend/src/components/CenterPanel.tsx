import { useSimulationStore } from '../stores/simulationStore'
import NetworkGraph from './NetworkGraph'
import MetricsDashboard from './MetricsDashboard'
import EventsTimeline from './EventsTimeline'

export default function CenterPanel() {
  const { simulation, topology, recentEvents } = useSimulationStore()

  if (!simulation) {
    return (
      <div className="center-area">
        <div className="panel" style={{ flex: 1 }}>
          <div className="panel-header">可视化区域</div>
          <div className="panel-content">
            <div className="empty-state">
              <div className="empty-state-icon">🔮</div>
              <div>创建推演场景后即可开始可视化分析</div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="center-area">
      <div className="panel visualization-area">
        <div className="panel-header">
          <span>Agent关系网络</span>
          <span style={{ fontWeight: 'normal', fontSize: '12px', color: '#999' }}>
            实时展示Agent间的互动关系
          </span>
        </div>
        <div className="panel-content" style={{ padding: 0 }}>
          <NetworkGraph topology={topology} agents={simulation.agents} />
        </div>
      </div>

      <MetricsDashboard metrics={simulation.metrics} />

      <EventsTimeline events={recentEvents} />
    </div>
  )
}
