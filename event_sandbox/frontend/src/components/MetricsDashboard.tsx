import type { SimulationMetrics } from '../types'

interface MetricsDashboardProps {
  metrics: SimulationMetrics | null
}

export default function MetricsDashboard({ metrics }: MetricsDashboardProps) {
  if (!metrics) {
    return (
      <div className="panel">
        <div className="panel-header">指标仪表盘</div>
        <div className="panel-content">
          <div className="empty-state">
            <div>暂无指标数据</div>
          </div>
        </div>
      </div>
    )
  }

  const metricCards = [
    {
      key: 'overall_sentiment',
      label: '整体情绪',
      value: metrics.overall_sentiment,
      format: (v: number) => (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%',
      className: metrics.overall_sentiment >= 0 ? 'positive' : 'negative',
    },
    {
      key: 'market_activity',
      label: '市场活跃度',
      value: metrics.market_activity,
      format: (v: number) => (v * 100).toFixed(1) + '%',
      className: '',
    },
    {
      key: 'cooperation_level',
      label: '合作水平',
      value: metrics.cooperation_level,
      format: (v: number) => (v * 100).toFixed(1) + '%',
      className: 'positive',
    },
    {
      key: 'conflict_level',
      label: '冲突程度',
      value: metrics.conflict_level,
      format: (v: number) => (v * 100).toFixed(1) + '%',
      className: v => v > 0.5 ? 'negative' : '',
    },
  ]

  return (
    <div className="panel">
      <div className="panel-header">
        <span>指标仪表盘</span>
        <span style={{ fontWeight: 'normal', fontSize: '12px', color: '#999' }}>
          实时监控推演指标变化
        </span>
      </div>
      <div className="panel-content">
        <div className="metrics-dashboard">
          {metricCards.map(card => (
            <div
              key={card.key}
              className={`metric-card ${typeof card.className === 'function' ? card.className(card.value) : card.className}`}
            >
              <div className="metric-value">
                {card.format(card.value)}
              </div>
              <div className="metric-label">{card.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
