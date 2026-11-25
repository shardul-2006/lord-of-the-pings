import { useEffect } from 'react'
import { CheckCircle, AlertOctagon, AlertTriangle, ShieldIcon } from './icons'

export interface ToastMessage {
  id: string
  title: string
  message: string
  type: 'success' | 'alert' | 'warning' | 'info'
}

interface Props {
  toasts: ToastMessage[]
  onDismiss: (id: string) => void
}

export function ToastContainer({ toasts, onDismiss }: Props) {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDismiss }: { toast: ToastMessage; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000)
    return () => clearTimeout(timer)
  }, [onDismiss])

  const Icon =
    toast.type === 'success' ? CheckCircle :
    toast.type === 'alert' ? AlertOctagon :
    toast.type === 'warning' ? AlertTriangle : ShieldIcon

  const borderColor =
    toast.type === 'success' ? '#10b981' :
    toast.type === 'alert' ? '#ef4444' :
    toast.type === 'warning' ? '#f59e0b' : '#3b82f6'

  return (
    <div
      className="toast-item slide-in-right"
      style={{ borderLeft: `3px solid ${borderColor}` }}
      onClick={onDismiss}
    >
      <div className="toast-icon">
        <Icon size={18} color={borderColor} />
      </div>
      <div className="toast-content">
        <div className="toast-title" style={{ color: borderColor }}>{toast.title}</div>
        <div className="toast-desc">{toast.message}</div>
      </div>
      <button className="toast-close" onClick={onDismiss}>&times;</button>
      <div className="toast-progress" style={{ background: borderColor }} />
    </div>
  )
}
