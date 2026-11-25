import type { ScanStatus } from '../types'
import { AlertOctagon, AlertTriangle, CheckCircle, SlashCircle } from './icons'

const BADGE_CONFIG: Record<ScanStatus, { color: string; label: string; Icon: typeof CheckCircle; pulse?: boolean }> = {
  clean:            { color: '#10b981', label: 'CLEAN',            Icon: CheckCircle },
  flagged:          { color: '#ef4444', label: 'FLAGGED',          Icon: AlertOctagon, pulse: true },
  review_required:  { color: '#f59e0b', label: 'REVIEW REQUIRED',  Icon: AlertTriangle },
  unsupported:      { color: '#64748b', label: 'UNSUPPORTED',      Icon: SlashCircle },
  scan_failed:      { color: '#64748b', label: 'SCAN FAILED',      Icon: SlashCircle },
}

interface Props {
  status: ScanStatus
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'sm' }: Props) {
  const cfg = BADGE_CONFIG[status] || BADGE_CONFIG.scan_failed
  const iconSize = size === 'sm' ? 12 : 15
  return (
    <span
      className={`status-badge status-badge--${size} status-badge--${status}`}
      style={{
        background: `linear-gradient(135deg, ${cfg.color}22, ${cfg.color}10)`,
        color: cfg.color,
        border: `1px solid ${cfg.color}55`,
        boxShadow: cfg.pulse ? `0 0 12px ${cfg.color}30` : undefined,
      }}
    >
      <cfg.Icon size={iconSize} color={cfg.color} />
      <span>{cfg.label}</span>
    </span>
  )
}
