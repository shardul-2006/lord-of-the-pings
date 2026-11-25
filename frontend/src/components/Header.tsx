import { useState, useEffect } from 'react'
import type { AppConfig } from '../types'
import { ShieldIcon, MenuIcon } from './icons'

interface Props {
  config: AppConfig
  onToggleSidebar: () => void
}

export function Header({ config, onToggleSidebar }: Props) {
  const [timeStr, setTimeStr] = useState<string>('')

  useEffect(() => {
    const update = () => {
      const now = new Date()
      const formatted = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        weekday: 'short',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(now)
      setTimeStr(`${formatted} IST`)
    }
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="header-brand">
          <button
            type="button"
            className="header-menu-btn"
            onClick={onToggleSidebar}
            aria-label="Toggle configuration sidebar"
            title="Toggle configuration sidebar"
          >
            <MenuIcon size={18} />
          </button>
          <div className="brand-logo-shield">
            <ShieldIcon size={30} />
            <span className="logo-glow-ring" />
          </div>
          <div>
            <div className="header-title">
              <span className="brand-rag">RAG-</span><span className="brand-shield">Shield</span>
            </div>
            <div className="header-subtitle">
              Cybersecurity for Document RAG
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
            Engine: <strong style={{ color: '#2dd4bf' }}>{config.llm.toUpperCase()}</strong>
          </span>

          <span className="meta-pill meta-pill--analyst">
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
      </div>
    </header>
  )
}
