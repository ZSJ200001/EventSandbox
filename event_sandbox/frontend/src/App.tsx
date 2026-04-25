import { useState, useEffect } from 'react'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { useSimulationStore } from './stores/simulationStore'
import Header from './components/Header'
import LeftSidebar from './components/LeftSidebar'
import CenterPanel from './components/CenterPanel'
import RightSidebar from './components/RightSidebar'
import LoadingOverlay from './components/LoadingOverlay'

function App() {
  const { isLoading, error, setError } = useSimulationStore()
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    // Check backend health on mount
    fetch('/api/health')
      .then(res => res.json())
      .then(data => {
        console.log('Backend health:', data)
        setInitialized(true)
      })
      .catch(err => {
        console.error('Backend not available:', err)
        setInitialized(true) // Still show UI even if backend is down
      })
  }, [])

  if (!initialized) {
    return (
      <ConfigProvider locale={zhCN}>
        <LoadingOverlay text="初始化中..." />
      </ConfigProvider>
    )
  }

  return (
    <ConfigProvider locale={zhCN}>
      <AntApp>
        <div className="app-container">
          <Header />
          {error && (
            <div style={{
              background: '#fff2f0',
              border: '1px solid #ffccc7',
              padding: '8px 16px',
              color: '#ff4d4f',
              fontSize: '14px'
            }}>
              错误: {error}
              <button
                onClick={() => setError(null)}
                style={{
                  float: 'right',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '16px'
                }}
              >
                ×
              </button>
            </div>
          )}
          <main className="app-main">
            <LeftSidebar />
            <CenterPanel />
            <RightSidebar />
          </main>
          {isLoading && <LoadingOverlay text="处理中..." />}
        </div>
      </AntApp>
    </ConfigProvider>
  )
}

export default App
