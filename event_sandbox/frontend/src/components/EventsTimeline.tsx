import type { Event } from '../types'

interface EventsTimelineProps {
  events: Event[]
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  action: '行动',
  reaction: '反应',
  external: '外部',
  intervention: '干预',
  system: '系统',
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  action: '#667eea',
  reaction: '#38ef7d',
  external: '#f7b731',
  intervention: '#f45c43',
  system: '#95a5a6',
}

export default function EventsTimeline({ events }: EventsTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="panel events-panel">
        <div className="panel-header">事件时间轴</div>
        <div className="panel-content">
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div>暂无事件记录</div>
            <div style={{ fontSize: '12px', marginTop: '4px' }}>
              点击"推进一回合"开始推演
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="panel events-panel">
      <div className="panel-header">
        <span>事件时间轴</span>
        <span style={{ fontWeight: 'normal', fontSize: '12px', color: '#999' }}>
          共 {events.length} 个事件
        </span>
      </div>
      <div className="panel-content" style={{ maxHeight: '220px', overflowY: 'auto' }}>
        {events.slice().reverse().map((event, idx) => (
          <div
            key={event.id}
            className="event-item"
            style={{ borderLeftColor: EVENT_TYPE_COLORS[event.type] || '#667eea' }}
          >
            <div className="event-round">
              <span style={{
                display: 'inline-block',
                padding: '1px 6px',
                background: EVENT_TYPE_COLORS[event.type] || '#667eea',
                color: 'white',
                borderRadius: '4px',
                fontSize: '10px',
                marginRight: '8px'
              }}>
                {EVENT_TYPE_LABELS[event.type] || event.type}
              </span>
              第 {event.round} 回合
              {idx === 0 && <span style={{ color: '#667eea', marginLeft: '8px' }}>NEW</span>}
            </div>
            <div className="event-description">{event.description}</div>
            {event.involved_agents.length > 0 && (
              <div className="event-agents">
                涉及: {event.involved_agents.join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
