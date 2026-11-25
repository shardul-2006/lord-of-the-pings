interface Props {
  value: number | string
  label: string
  sub?: string
  color?: string
  borderColor?: string
  icon?: string
}

export function MetricCard({ value, label, sub, color, borderColor }: Props) {
  const accent = color || '#14b8a6'

  return (
    <div
      className="metric-card fade-in"
      style={{
        '--card-accent': accent,
        borderBottom: borderColor ? `2px solid ${borderColor}` : undefined,
      } as React.CSSProperties}
    >
      <div className="metric-glow-bar" style={{ background: accent }} />
      <div className="metric-header-row">
        <div className="metric-value" style={{ color: accent }}>{value}</div>
        <div className="metric-pulse-dot" style={{ background: accent }} />
      </div>
      <div className="metric-label">{label}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      <div className="metric-mini-meter">
        <div className="metric-mini-fill" style={{ background: accent, width: typeof value === 'number' && value > 0 ? '70%' : '20%' }} />
      </div>
    </div>
  )
}
