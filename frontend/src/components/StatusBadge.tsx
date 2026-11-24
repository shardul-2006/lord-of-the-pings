import type { ScanStatus } from '../types'
import { AlertOctagon, AlertTriangle, CheckCircle, SlashCircle } from './icons'

const BADGE_CONFIG: Record<ScanStatus, { color: string; label: string; Icon: typeof CheckCircle }> = {
  clean:            { color: '#10b981', label: 'CLEAN',              Icon: CheckCircle },
  flagged:          { color: '#ef4444', label: 'FLAGGED',            Icon: AlertOctagon },
  review_required:  { color: '#f59e0b', label: 'REVIEW REQUIRED',   Icon: AlertTriangle },
  unsupported:      { color: '#64748b', label: 'UNSUPPORTED',        Icon: SlashCircle },
  scan_failed:      { color: '#64748b', label: 'SCAN FAILED',        Icon: SlashCircle },
}

interface Props {
  status: ScanStatus
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'sm' }: Props) {
  const cfg = BADGE_CONFIG[status] || BADGE_CONFIG.scan_failed
  const iconSize = size === 'sm' ? 12 : 16
  return (
    <span
      className={`status-badge status-badge--${size}`}
      style={{
        background: `${cfg.color}18`,
        color: cfg.color,
        border: `1px solid ${cfg.color}40`,
      }}
    >
      <cfg.Icon size={iconSize} color={cfg.color} />
      {cfg.label}
    </span>
  )
}
