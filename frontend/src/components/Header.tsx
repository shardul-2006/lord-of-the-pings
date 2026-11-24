import type { AppConfig } from '../types'
import { ShieldIcon } from './icons'

interface Props {
  config: AppConfig
}

export function Header({ config }: Props) {
  return (
    <header className="app-header">
      <div className="header-brand">
        <ShieldIcon size={22} />
        <div>
          <div className="header-title">RAG-SHIELD // TRUST LAYER</div>
          <div className="header-subtitle">Provenance-Aware Security Middleware for Document RAG</div>
        </div>
        <span className="header-policy-tag">policy_v1</span>
      </div>
      <div className="header-meta">
        <span className="meta-pill">
          <span className="status-dot status-dot--active" /> Tier: <strong>{config.tier}</strong>
        </span>
        <span className="meta-pill">Model: <strong>{config.llm}</strong></span>
        <span className="meta-pill">Analyst: <strong>{config.analyst}</strong></span>
      </div>
    </header>
  )
}
