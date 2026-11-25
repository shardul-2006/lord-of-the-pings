import { useState, useEffect } from 'react'
import type { AppConfig } from '../types'
import { ShieldIcon } from './icons'

interface Props {
  config: AppConfig
}

export function Header({ config }: Props) {
  const [timeStr, setTimeStr] = useState<string>('')

  useEffect(() => {
    const update = () => {
      const now = new Date()
      setTimeStr(now.toUTCString().replace('GMT', 'UTC'))
    }
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-logo-shield">
          <ShieldIcon size={24} />
          <span className="logo-glow-ring" />
        </div>
        <div>
          <div className="header-title">
            RAG-SHIELD <span className="title-slash">//</span> TRUST LAYER
          </div>
          <div className="header-subtitle">
            Provenance-Aware Security Middleware for Document RAG
          </div>
        </div>
        <span className="header-policy-tag">policy_v1</span>
      </div>

      <div className="header-meta">
        <div className="meta-clock telemetry-mono">
          <span className="clock-pulse-dot" />
          {timeStr || 'SYSTEM ONLINE'}
        </div>

        <span className="meta-pill">
          <span className="status-dot status-dot--active" /> Tier: <strong>{config.tier}</strong>
        </span>

        <span className="meta-pill">
          Engine: <strong style={{ color: '#60a5fa' }}>{config.llm.toUpperCase()}</strong>
        </span>

        <span className="meta-pill">
          Analyst: <strong>{config.analyst}</strong>
        </span>

        <a
          href="http://localhost:8501"
          target="_blank"
          rel="noreferrer"
          className="meta-link-btn"
          title="Open Streamlit Console"
        >
          Streamlit (8501) &rarr;
        </a>
      </div>
    </header>
  )
}
