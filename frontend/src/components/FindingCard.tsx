import { useState } from 'react'
import type { Finding, ScanStatus } from '../types'
import { StatusBadge } from './StatusBadge'
import { ChevronDown } from './icons'

interface Props {
  finding: Finding
  text: string
  status: ScanStatus | 'released' | 'quarantined'
  onRelease?: () => void
  analyst?: string
}

export function FindingCard({ finding, text, status, onRelease, analyst }: Props) {
  const [expanded, setExpanded] = useState(false)

  const hasH = finding.signals.some(s => ['tiny_font', 'low_contrast', 'off_page'].includes(s.type))
  const hasC = finding.signals.some(s => ['metadata', 'alt_text'].includes(s.type))
  const hVal = hasH ? 0.40 : 0
  const cVal = hasC ? 0.20 : 0
  const rem = Math.max(0, finding.score - hVal - cVal)
  const sVal = Math.min(0.45, rem * 0.55)
  const lVal = Math.max(0, rem - sVal)

  const badgeStatus: ScanStatus =
    status === 'quarantined' ? 'flagged' :
    status === 'released' ? 'clean' :
    (status as ScanStatus)

  const borderClass =
    status === 'quarantined' || status === 'flagged' ? 'finding--flagged' :
    status === 'review_required' ? 'finding--review' :
    status === 'released' ? 'finding--released' : 'finding--clean'

  return (
    <div className={`finding-card ${borderClass} fade-in`}>
      <div className="finding-header" onClick={() => setExpanded(!expanded)}>
        <div className="finding-header-left">
          <StatusBadge status={badgeStatus} />
          <code className="finding-id">{finding.sentence_id}</code>
        </div>
        <div className="finding-header-right">
          <span className="finding-score">Score: {finding.score.toFixed(3)}</span>
          <ChevronDown
            size={14}
            className={`finding-chevron ${expanded ? 'rotated' : ''}`}
          />
        </div>
      </div>

      <div className="finding-text">
        &ldquo;{text}&rdquo;
      </div>

      <div className={`finding-details ${expanded ? 'expanded' : ''}`}>
        <div className="signal-grid">
          {[
            { label: 'Hiding (H)', val: hVal, color: '#ef4444' },
            { label: 'Directive (L)', val: lVal, color: '#f59e0b' },
            { label: 'Classifier (S)', val: sVal, color: '#3b82f6' },
            { label: 'Carrier (C)', val: cVal, color: '#8b5cf6' },
          ].map(({ label, val, color }) => (
            <div key={label} className="signal-cell">
              <div className="signal-label">{label}</div>
              <div className="signal-value" style={{ color: val > 0 ? color : '#64748b' }}>
                {val.toFixed(2)}
              </div>
            </div>
          ))}
        </div>

        <div className="finding-signals">
          <strong>Signals:</strong> {finding.signals.map(s => s.type).join(', ') || 'None'}
          &nbsp;&middot;&nbsp;
          <strong>Rationale:</strong> {finding.decision_reason}
        </div>

        {(status === 'quarantined' || status === 'flagged' || status === 'review_required') && onRelease && (
          <div className="finding-actions">
            <button className="btn btn--sm btn--outline" onClick={(e) => { e.stopPropagation(); onRelease() }}>
              Release Sentence
            </button>
            <span className="finding-action-hint">
              Release false positive to re-index (audited under {analyst}).
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
