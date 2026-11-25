import type { ScanStatus, IngestResult } from '../types'
import { StatusBadge } from './StatusBadge'
import { AlertOctagon, AlertTriangle, CheckCircle, SlashCircle } from './icons'

const BLOCKED: ScanStatus[] = ['unsupported', 'scan_failed']

interface Props {
  result: IngestResult
  filename: string
}

export function PostureCard({ result, filename }: Props) {
  const { status, quarantined_ids = [], review_ids = [], doc_id, index_version, reason } = result
  const isBlocked = BLOCKED.includes(status)

  const headline = isBlocked
    ? `Blocked: ${reason || 'Unsupported File'}`
    : status === 'flagged'
    ? `Threat Isolated: ${quarantined_ids.length} Malicious Sentence(s) Quarantined`
    : status === 'review_required'
    ? `Operator Review Required: ${review_ids.length} Sentence(s) Held`
    : 'Verified Clean: Permitted Document Facts Retained in Defended Index'

  const Icon = isBlocked ? SlashCircle
    : status === 'flagged' ? AlertOctagon
    : status === 'review_required' ? AlertTriangle
    : CheckCircle

  const themeClass = isBlocked ? 'posture--blocked'
    : status === 'flagged' ? 'posture--flagged'
    : status === 'review_required' ? 'posture--review'
    : 'posture--clean'

  const accentColor = isBlocked ? '#64748b'
    : status === 'flagged' ? '#ef4444'
    : status === 'review_required' ? '#f59e0b'
    : '#10b981'

  return (
    <div className={`posture-card ${themeClass} slide-up`}>
      <div className="posture-icon-wrapper" style={{ borderColor: `${accentColor}55` }}>
        <Icon size={24} color={accentColor} />
        <span className="posture-ping-ring" style={{ borderColor: accentColor }} />
      </div>
      <div className="posture-body">
        <div className="posture-headline">
          <strong>{headline}</strong>
          <StatusBadge status={status} size="md" />
        </div>
        <div className="posture-meta">
          <span className="posture-chip">Target: <strong>{filename}</strong></span>
          <span className="posture-chip">Doc ID: <code>{doc_id?.slice(0, 12)}...</code></span>
          <span className="posture-chip">Index: <code>v{index_version || 1}</code></span>
          <span className="posture-chip">Disposition: <strong>{status.toUpperCase()}</strong></span>
        </div>
      </div>
    </div>
  )
}
