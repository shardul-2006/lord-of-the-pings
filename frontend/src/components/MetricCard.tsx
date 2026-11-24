interface Props {
  value: number | string
  label: string
  sub?: string
  color?: string
  borderColor?: string
}

export function MetricCard({ value, label, sub, color, borderColor }: Props) {
  return (
    <div
      className="metric-card fade-in"
      style={{ borderBottom: borderColor ? `2px solid ${borderColor}` : undefined }}
    >
      <div className="metric-value" style={{ color: color || '#f8fafc' }}>{value}</div>
      <div className="metric-label">{label}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  )
}
