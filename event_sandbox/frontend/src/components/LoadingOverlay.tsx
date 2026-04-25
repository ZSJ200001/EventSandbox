interface LoadingOverlayProps {
  text?: string
}

export default function LoadingOverlay({ text = '加载中...' }: LoadingOverlayProps) {
  return (
    <div className="loading-overlay">
      <div className="loading-spinner" />
      <div className="loading-text">{text}</div>
    </div>
  )
}
