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
  { key: 'clean', desc: 'Scan completed, low risk. All facts eligible.' },
  { key: 'flagged', desc: 'High-risk sentences quarantined. Facts preserved.' },
  { key: 'review_required', desc: 'Ambiguous text held pending operator review.' },
  { key: 'unsupported', desc: 'Fail-closed: rejected from index.' },
  { key: 'scan_failed', desc: 'Scan errored or timed out. Blocked.' },
]

export function Sidebar({ open, config, onConfigChange, onToggle }: Props) {
  return (
    <>
      {open && <div className="sidebar-backdrop" onClick={onToggle} aria-hidden="true" />}
      <button className="sidebar-toggle" onClick={onToggle} aria-label="Toggle sidebar">
        {open ? '\u2039' : '\u203A'}
      </button>
      <aside className={`sidebar ${open ? 'open' : 'closed'}`}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">
            <ShieldIcon size={26} />
          </div>
          <div>
            <div className="sidebar-brand-name">
              <span className="brand-rag">RAG-</span><span className="brand-shield">Shield</span>
            </div>
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
            <option value="external_upload">external_upload (Strict)</option>
            <option value="internal_kb">internal_kb (Relaxed)</option>
          </select>
          <div className="tier-spec-card">
            {config.tier === 'external_upload' ? (
              <>
                <div className="tier-spec-row">
                  <span className="tier-badge-lock"><LockIcon size={12} /> Strict Policy</span>
                  <span className="tier-val">&ge;0.70 Quarantine</span>
                </div>
                <p className="tier-spec-desc">
                  Active defense: Dynamic Nonce Delimiters (Layer 3) &amp; strict thresholds (0.70 / 0.40).
                </p>
              </>
            ) : (
              <>
                <div className="tier-spec-row">
                  <span className="tier-badge-unlock"><UnlockIcon size={12} /> Internal Docs</span>
                  <span className="tier-val">&ge;0.90 Quarantine</span>
                </div>
                <p className="tier-spec-desc">
                  Permissive mode for internal technical wikis with relaxed thresholds (0.90 / 0.80).
                </p>
              </>
            )}
          </div>

          <label className="field-label">Language Model Engine</label>
          <select
            className="field-select"
            value={config.llm}
            onChange={(e) => onConfigChange({ ...config, llm: e.target.value as AppConfig['llm'] })}
          >
            <option value="mock">mock (Deterministic Security Double)</option>
            <option value="real">real (Ollama / Local Llama 3.1 8B)</option>
          </select>

          <label className="field-label">Security Analyst Identity</label>
          <input
            className="field-input"
            value={config.analyst}
            onChange={(e) => onConfigChange({ ...config, analyst: e.target.value })}
            placeholder="e.g., alice.chen@secops"
          />
        </div>

        <hr className="sidebar-divider" />

        <div className="sidebar-section">
          <h3 className="sidebar-heading">Status Taxonomy</h3>
          {STATUSES.map((s) => (
            <div key={s.key} className="legend-item">
              <StatusBadge status={s.key} />
              <span className="legend-desc">{s.desc}</span>
            </div>
          ))}
        </div>

        <hr className="sidebar-divider" />
        <div className="sidebar-footer">
          <div className="footer-spec-row"><span>Policy Engine:</span> <code>policy_v1</code></div>
          <div className="footer-spec-row"><span>Taxonomy:</span> <code>OWASP:ASI-01</code> &middot; <code>ATLAS</code></div>
          <div className="footer-spec-row"><span>Forensic Ledger:</span> <code>SQLite Local</code></div>
        </div>
      </aside>
    </>
  )
}
