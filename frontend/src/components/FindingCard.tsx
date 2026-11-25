import { useState } from 'react'
import type { Finding, ScanStatus } from '../types'
import { StatusBadge } from './StatusBadge'
import { ChevronDown } from './icons'
import { RiskMeter } from './RiskMeter'

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
          <span className="finding-threat-tag">
            {finding.score >= 0.70 ? 'CRITICAL RISK' : finding.score >= 0.40 ? 'SUSPICIOUS' : 'BENIGN FACT'}
          </span>
        </div>
        <div className="finding-header-right">
          <div style={{ width: 140, marginRight: 10 }}>
            <RiskMeter score={finding.score} size="sm" showLabels={false} />
          </div>
          <span className="finding-score">Score: {finding.score.toFixed(3)}</span>
          <ChevronDown
            size={14}
            className={`finding-chevron ${expanded ? 'rotated' : ''}`}
          />
        </div>
      </div>

      <div className="finding-text">
        <span className="quote-mark">&ldquo;</span>
        {text}
        <span className="quote-mark">&rdquo;</span>
      </div>

      <div className={`finding-details ${expanded ? 'expanded' : ''}`}>
        <div className="telemetry-bar-row">
          <div className="signal-cell-meter">
            <div className="signal-cell-header">
              <span>Hiding (H)</span>
              <span className="telemetry-mono" style={{ color: hVal > 0 ? '#ef4444' : '#64748b' }}>{hVal.toFixed(2)}</span>
            </div>
            <div className="mini-track">
              <div className="mini-bar" style={{ width: `${(hVal / 0.40) * 100}%`, background: '#ef4444' }} />
            </div>
          </div>

          <div className="signal-cell-meter">
            <div className="signal-cell-header">
              <span>Directive (L)</span>
              <span className="telemetry-mono" style={{ color: lVal > 0 ? '#f59e0b' : '#64748b' }}>{lVal.toFixed(2)}</span>
            </div>
            <div className="mini-track">
              <div className="mini-bar" style={{ width: `${Math.min(100, (lVal / 0.35) * 100)}%`, background: '#f59e0b' }} />
            </div>
          </div>

          <div className="signal-cell-meter">
            <div className="signal-cell-header">
              <span>Classifier (S)</span>
              <span className="telemetry-mono" style={{ color: sVal > 0 ? '#3b82f6' : '#64748b' }}>{sVal.toFixed(2)}</span>
            </div>
            <div className="mini-track">
              <div className="mini-bar" style={{ width: `${Math.min(100, (sVal / 0.45) * 100)}%`, background: '#3b82f6' }} />
            </div>
          </div>

          <div className="signal-cell-meter">
            <div className="signal-cell-header">
              <span>Carrier (C)</span>
              <span className="telemetry-mono" style={{ color: cVal > 0 ? '#8b5cf6' : '#64748b' }}>{cVal.toFixed(2)}</span>
            </div>
            <div className="mini-track">
              <div className="mini-bar" style={{ width: `${(cVal / 0.20) * 100}%`, background: '#8b5cf6' }} />
            </div>
          </div>
        </div>

        <div className="finding-signals">
          <strong>Signals Detected:</strong>{' '}
          {finding.signals.map(s => (
            <span key={s.type} className="signal-chip">{s.type}</span>
          )) || 'None'}
          <br />
          <strong>Forensic Rationale:</strong> {finding.decision_reason}
        </div>

        {(status === 'quarantined' || status === 'flagged' || status === 'review_required') && onRelease && (
          <div className="finding-actions">
            <button className="btn btn--sm btn--primary-glow" onClick={(e) => { e.stopPropagation(); onRelease() }}>
              Release to Defended Index
            </button>
            <span className="finding-action-hint">
              Reversible: signs release event under Analyst <strong>{analyst}</strong> in SQLite Trust Ledger.
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
