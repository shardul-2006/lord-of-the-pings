const LAYERS = [
  {
    layer: '01',
    tag: 'INGESTION GUARD',
    title: 'Canonicalization & Physical Hiding',
    color: '#3b82f6',
    items: [
      'Fail-closed scanner guard: size, page, timeout limits',
      'Layout signals: tiny_font, low_contrast, off_page',
      'Metadata and alt-text carrier extraction',
      'Unicode normalization preserving Indic ZWJ/ZWNJ',
    ],
  },
  {
    layer: '02',
    tag: 'SURGICAL FUSION',
    title: 'Sentence-Level Scoring & Fusion',
    color: '#8b5cf6',
    items: [
      'Multi-vector risk fusion: S, L, H, C signals',
      'Surgical quarantine: only risky sentences withheld',
      'Reversible isolation with provenance tracking',
      'Configurable thresholds per trust tier',
    ],
  },
  {
    layer: '03',
    tag: 'BOUNDARY ISOLATION',
    title: 'Context Isolation & Spotlighting',
    color: '#f59e0b',
    items: [
      'Trust tiers: external_upload vs internal_kb',
      'Dynamic nonce delimiter spotlighting',
      'Per-request cryptographic boundary isolation',
      'Defended retrieval index management',
    ],
  },
  {
    layer: '04',
    tag: 'EGRESS SAFEGUARD',
    title: 'Output Validation & Safeguards',
    color: '#10b981',
    items: [
      'Canary token injection and redaction',
      'Data exfiltration link stripping',
      'Citation grounding verification',
      'Exfiltration image tag detection',
    ],
  },
]

export function Architecture() {
  return (
    <div className="console-page architecture-page">
      <div className="page-header-row">
        <div className="page-title-block">
          <h2 className="page-title">RAG-Shield 4-Layer Security Architecture</h2>
          <p className="page-desc">
            A modular security middleware that prevents indirect prompt injection
            without discarding legitimate documents. Operates at the sentence level.
          </p>
        </div>
        <div className="quick-stats-pill">
          <span className="live-radar-dot" />
          <span>DEFENSE IN DEPTH</span>
        </div>
      </div>

      <div className="arch-grid">
        {LAYERS.map(({ layer, tag, title, color, items }) => (
          <div
            key={layer}
            className="arch-card hud-box fade-in"
            style={{ '--arch-color': color, borderTop: `3px solid ${color}` } as React.CSSProperties}
          >
            <span className="hud-corner hud-corner--tl" />
            <span className="hud-corner hud-corner--tr" />
            <div className="arch-card-header">
              <div className="arch-layer-num" style={{ color }}>LAYER {layer}</div>
              <span
                className="arch-layer-tag"
                style={{ color, background: `${color}18`, borderColor: `${color}45` }}
              >
                {tag}
              </span>
            </div>
            <h3 className="arch-title">{title}</h3>
            <ul className="arch-list">
              {items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
