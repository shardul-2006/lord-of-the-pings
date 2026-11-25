import { useEffect, useState } from 'react'

interface Props {
  filename: string
  stage?: string
}

const STAGES = [
  'Verifying binary magic bytes and file bounds...',
  'Extracting geometric font coordinates & off-page bounds (Layer 1)...',
  'Analyzing luminance contrast ratios & carrier metadata...',
  'Segmenting sentences & executing multi-vector fusion (Layer 2)...',
  'Syncing SQLite Trust Ledger & locking defended vector index (Layer 3)...',
]

export function ScanProgress({ filename, stage }: Props) {
  const [stageIdx, setStageIdx] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setStageIdx((prev) => (prev < STAGES.length - 1 ? prev + 1 : prev))
    }, 700)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="scan-radar-card slide-up">
      <div className="radar-header">
        <div className="radar-status-pulse">
          <span className="radar-ping" />
          <span className="radar-dot" />
        </div>
        <div className="radar-meta">
          <div className="radar-title">ACTIVE SECURITY SCANNER // MULTI-LAYER ANALYSIS</div>
          <div className="radar-target">
            Target: <strong>{filename}</strong> &middot; <span className="telemetry-mono">DEFENSE ENGAGED</span>
          </div>
        </div>
        <div className="radar-counter">
          STEP {stageIdx + 1} OF {STAGES.length}
        </div>
      </div>

      {/* Futuristic Laser Scan Track */}
      <div className="laser-scanner-track">
        <div className="laser-beam" />
        <div
          className="laser-progress-fill"
          style={{ width: `${((stageIdx + 1) / STAGES.length) * 100}%` }}
        />
      </div>

      <div className="radar-telemetry-box">
        <div className="radar-log-current">
          <span className="log-chevron">&gt;&gt;</span> {stage || STAGES[stageIdx]}
        </div>
        <div className="radar-steps-grid">
          {STAGES.map((s, i) => (
            <div
              key={i}
              className={`radar-step-badge ${i < stageIdx ? 'complete' : i === stageIdx ? 'active' : 'pending'}`}
            >
              <span className="step-num">0{i + 1}</span>
              <span className="step-name">{s.split(' ')[0]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
