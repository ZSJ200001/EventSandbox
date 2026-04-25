import { useState } from 'react'
import { Input, Button } from 'antd'
import { useSimulationStore } from '../stores/simulationStore'

const { TextArea } = Input

export default function LeftSidebar() {
  const {
    simulation,
    createSimulation,
    stepSimulation,
    isRunning,
  } = useSimulationStore()

  const [name, setName] = useState('奶茶涨价事件推演')
  const [description, setDescription] = useState('')
  const [eventText, setEventText] = useState('')
  const [showCreate, setShowCreate] = useState(true)

  const handleCreate = async () => {
    if (!eventText.trim()) {
      alert('请输入事件描述')
      return
    }
    try {
      await createSimulation(name, description, eventText)
      setShowCreate(false)
    } catch (e) {
      console.error('创建失败:', e)
    }
  }

  const handleStep = async () => {
    try {
      await stepSimulation()
    } catch (e) {
      console.error('推进失败:', e)
    }
  }

  const handleReset = () => {
    setShowCreate(true)
    setEventText('')
    useSimulationStore.getState().reset()
  }

  return (
    <aside className="panel left-sidebar">
      <div className="panel-header">
        <span>场景设置</span>
      </div>
      <div className="panel-content">
        {showCreate || !simulation ? (
          <div>
            <div className="input-group">
              <label>场景名称</label>
              <Input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="输入场景名称"
              />
            </div>
            <div className="input-group">
              <label>场景描述</label>
              <TextArea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="简要描述场景背景（可选）"
                rows={2}
              />
            </div>
            <div className="input-group">
              <label>事件描述 *</label>
              <TextArea
                value={eventText}
                onChange={e => setEventText(e.target.value)}
                placeholder="粘贴新闻或事件描述，例如：XX奶茶招牌产品涨价3元"
                rows={4}
              />
            </div>
            <Button
              type="primary"
              onClick={handleCreate}
              style={{ width: '100%', marginTop: '8px' }}
              disabled={!eventText.trim()}
            >
              创建推演场景
            </Button>
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: '12px' }}>
              <strong>场景:</strong> {simulation.name}
            </div>
            <div style={{ marginBottom: '12px' }}>
              <strong>状态:</strong> {simulation.status}
            </div>
            <div style={{ marginBottom: '12px' }}>
              <strong>智能体数量:</strong> {simulation.agents.length}
            </div>
            <div style={{ marginBottom: '12px' }}>
              <strong>当前回合:</strong> {simulation.current_round} / {simulation.rounds}
            </div>

            <div className="controls" style={{ marginTop: '16px' }}>
              <Button
                type="primary"
                onClick={handleStep}
                disabled={isRunning || simulation.status === 'completed'}
                style={{ flex: 1 }}
              >
                {simulation.status === 'completed' ? '已完成' : '推进一回合'}
              </Button>
              <Button onClick={handleReset}>
                重置
              </Button>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
