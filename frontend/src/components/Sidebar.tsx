import type { AppConfig } from '../types'
import { ShieldIcon, LockIcon, UnlockIcon } from './icons'
import { StatusBadge } from './StatusBadge'
import type { ScanStatus } from '../types'

interface Props {
  open: boolean
  config: AppConfig
  onConfigChange: (c: AppConfig) => void
  onToggle: () => void
}

const STATUSES: { key: ScanStatus; desc: string }[] = [
  { key: 'clean', desc: 'Scan completed, low risk.' },
  { key: 'flagged', desc: 'High-risk sentences quarantined.' },
  { key: 'review_required', desc: 'Held pending operator review.' },
  { key: 'unsupported', desc: 'Fail-closed: rejected.' },
  { key: 'scan_failed', desc: 'Scan errored. Blocked.' },
]

export function Sidebar({ open, config, onConfigChange, onToggle }: Props) {
  return (
    <>
      <button className="sidebar-toggle" onClick={onToggle} aria-label="Toggle sidebar">
        {open ? '\u2039' : '\u203A'}
      </button>
      <aside className={`sidebar ${open ? 'open' : 'closed'}`}>
        <div className="sidebar-brand">
          <ShieldIcon size={20} />
          <div>
            <div className="sidebar-brand-name">RAG-Shield Console</div>
            <div className="sidebar-brand-sub">Security Operations</div>
          </div>
        </div>

        <div className="sidebar-section">
          <h3 className="sidebar-heading">Configuration &amp; Policy</h3>

          <label className="field-label">Source Trust Tier</label>
          <select
            className="field-select"
            value={config.tier}
            onChange={(e) => onConfigChange({ ...config, tier: e.target.value as AppConfig['tier'] })}
          >
            <option value="external_upload">external_upload</option>
            <option value="internal_kb">internal_kb</option>
          </select>
          <p className="field-hint">
            {config.tier === 'external_upload' ? (
              <><LockIcon size={12} /> Strict: Quarantine &ge;0.70 &middot; Review &ge;0.40</>
            ) : (
              <><UnlockIcon size={12} /> Relaxed: internal documentation thresholds</>
            )}
          </p>

          <label className="field-label">Language Model</label>
          <select
            className="field-select"
            value={config.llm}
            onChange={(e) => onConfigChange({ ...config, llm: e.target.value as AppConfig['llm'] })}
          >
            <option value="mock">mock</option>
            <option value="real">real</option>
          </select>

          <label className="field-label">Security Analyst ID</label>
          <input
            className="field-input"
            value={config.analyst}
            onChange={(e) => onConfigChange({ ...config, analyst: e.target.value })}
          />
        </div>

        <hr className="sidebar-divider" />

        <div className="sidebar-section">
          <h3 className="sidebar-heading">Status Legend</h3>
          {STATUSES.map((s) => (
            <div key={s.key} className="legend-item">
              <StatusBadge status={s.key} />
              <span className="legend-desc">{s.desc}</span>
            </div>
          ))}
        </div>

        <hr className="sidebar-divider" />
        <div className="sidebar-footer">
          <div>Policy Engine: <code>policy_v1</code></div>
          <div>Forensic Ledger: SQLite Local</div>
        </div>
      </aside>
    </>
  )
}
