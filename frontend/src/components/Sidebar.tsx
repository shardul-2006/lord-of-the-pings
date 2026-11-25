import type { AppConfig, ScanStatus } from '../types'
import { ShieldIcon, LockIcon, UnlockIcon, SettingsIcon, TagIcon, TerminalIcon } from './icons'
import { StatusBadge } from './StatusBadge'

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
      <button className="sidebar-toggle" onClick={onToggle} aria-label="Toggle sidebar">
        {open ? '\u2039' : '\u203A'}
      </button>
      <aside className={`sidebar ${open ? 'open' : 'closed'}`}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">
            <ShieldIcon size={22} />
          </div>
          <div>
            <div className="sidebar-brand-name">RAG-Shield Console</div>
            <div className="sidebar-brand-sub">Security Operations Command</div>
          </div>
        </div>

        <div className="sidebar-panel-card">
          <div className="sidebar-heading-row">
            <SettingsIcon size={13} color="#60a5fa" />
            <h3 className="sidebar-heading">Configuration &amp; Policy</h3>
          </div>

          <label className="field-label">Source Trust Tier</label>
          <div className="option-pill-group" role="radiogroup" aria-label="Source Trust Tier">
            <button
              type="button"
              className={`option-card-btn ${config.tier === 'external_upload' ? 'active active--amber' : ''}`}
              onClick={() => onConfigChange({ ...config, tier: 'external_upload' })}
            >
              <div className="option-card-top">
                <span className="option-card-title">
                  <LockIcon size={12} /> External
                </span>
                <span className="option-card-code">STRICT</span>
              </div>
              <span className="option-card-sub">0.70 / 0.40 &middot; Nonce</span>
            </button>
            <button
              type="button"
              className={`option-card-btn ${config.tier === 'internal_kb' ? 'active active--green' : ''}`}
              onClick={() => onConfigChange({ ...config, tier: 'internal_kb' })}
            >
              <div className="option-card-top">
                <span className="option-card-title">
                  <UnlockIcon size={12} /> Internal KB
                </span>
                <span className="option-card-code">RELAXED</span>
              </div>
              <span className="option-card-sub">0.90 / 0.80 &middot; Wiki</span>
            </button>
          </div>

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
          <div className="option-pill-group" role="radiogroup" aria-label="Language Model Engine">
            <button
              type="button"
              className={`option-card-btn ${config.llm === 'mock' ? 'active active--blue' : ''}`}
              onClick={() => onConfigChange({ ...config, llm: 'mock' })}
            >
              <div className="option-card-top">
                <span className="option-card-title">Mock Double</span>
                <span className="option-card-code">FAST</span>
              </div>
              <span className="option-card-sub">Deterministic</span>
            </button>
            <button
              type="button"
              className={`option-card-btn ${config.llm === 'real' ? 'active active--purple' : ''}`}
              onClick={() => onConfigChange({ ...config, llm: 'real' })}
            >
              <div className="option-card-top">
                <span className="option-card-title">Local LLM</span>
                <span className="option-card-code">OLLAMA</span>
              </div>
              <span className="option-card-sub">Llama 3.1 8B</span>
            </button>
          </div>

          <label className="field-label">Security Analyst Identity</label>
          <input
            className="field-input"
            value={config.analyst}
            onChange={(e) => onConfigChange({ ...config, analyst: e.target.value })}
            placeholder="Analyst ID for trust ledger..."
          />
        </div>

        <div className="sidebar-panel-card">
          <div className="sidebar-heading-row">
            <TagIcon size={13} color="#60a5fa" />
            <h3 className="sidebar-heading">Status Taxonomy</h3>
          </div>
          <div className="legend-list">
            {STATUSES.map((s) => (
              <div key={s.key} className="legend-item">
                <StatusBadge status={s.key} />
                <span className="legend-desc">{s.desc}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="sidebar-panel-card sidebar-footer-card">
          <div className="sidebar-heading-row">
            <TerminalIcon size={13} color="#60a5fa" />
            <h3 className="sidebar-heading">Runtime Telemetry</h3>
          </div>
          <div className="sidebar-footer">
            <div className="footer-spec-row"><span>Policy Engine</span> <code>policy_v1</code></div>
            <div className="footer-spec-row"><span>Taxonomy</span> <code>OWASP:ASI-01</code></div>
            <div className="footer-spec-row"><span>Forensic Ledger</span> <code>SQLite Local</code></div>
          </div>
        </div>
      </aside>
    </>
  )
}
