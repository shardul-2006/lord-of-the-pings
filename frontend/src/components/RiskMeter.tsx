interface Props {
  score: number // 0.0 to 1.0
  size?: 'sm' | 'md'
  showLabels?: boolean
}

export function RiskMeter({ score, size = 'md', showLabels = true }: Props) {
  const pct = Math.min(100, Math.max(0, score * 100))
  const color =
    score >= 0.70 ? '#ef4444' :
    score >= 0.40 ? '#f59e0b' : '#10b981'

  const height = size === 'sm' ? 6 : 10

  return (
    <div className="risk-meter-wrapper">
      <div className="risk-meter-track" style={{ height }}>
        <div
          className="risk-meter-fill"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, #10b981 0%, #f59e0b 50%, #ef4444 100%)`,
            boxShadow: `0 0 10px ${color}80`,
          }}
        />
        {/* Threshold Markers */}
        <div className="risk-meter-marker" style={{ left: '40%' }} title="Review Threshold (0.40)">
          <span className="marker-pin" />
        </div>
        <div className="risk-meter-marker" style={{ left: '70%' }} title="Quarantine Threshold (0.70)">
          <span className="marker-pin marker-pin--danger" />
        </div>
      </div>
      {showLabels && (
        <div className="risk-meter-labels">
          <span style={{ color: '#10b981' }}>Safe (0.0)</span>
          <span style={{ color: '#f59e0b' }}>Review (0.40)</span>
          <span style={{ color: '#ef4444' }}>Quarantine (0.70)</span>
          <span style={{ fontWeight: 700, color }}>{score.toFixed(3)}</span>
        </div>
      )}
    </div>
  )
}
