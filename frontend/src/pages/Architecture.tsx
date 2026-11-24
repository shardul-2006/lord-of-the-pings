export function Architecture() {
  return (
    <div className="console-page architecture-page">
      <h2 className="page-title">RAG-Shield 4-Layer Security Architecture</h2>
      <p className="page-desc">
        A modular security middleware that prevents indirect prompt injection
        without discarding legitimate documents. Operates at the sentence level.
      </p>

      <div className="arch-grid">
        {[
          {
            layer: '1',
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
            layer: '2',
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
            layer: '3',
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
            layer: '4',
            title: 'Output Validation & Safeguards',
            color: '#10b981',
            items: [
              'Canary token injection and redaction',
              'Data exfiltration link stripping',
              'Citation grounding verification',
              'Exfiltration image tag detection',
            ],
          },
        ].map(({ layer, title, color, items }) => (
          <div key={layer} className="arch-card fade-in" style={{ borderTop: `3px solid ${color}` }}>
            <div className="arch-layer-num" style={{ color }}>{layer}</div>
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
