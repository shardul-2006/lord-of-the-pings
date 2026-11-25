import { useState, useCallback, useRef } from 'react'
import type { AppConfig, IngestResult, Finding, ReviewItem, DocumentMeta, ScanStatus, SampleInfo, IntegrityResult } from '../types'
import * as api from '../api'
import { DropZone } from '../components/DropZone'
import { ScanProgress } from '../components/ScanProgress'
import { PostureCard } from '../components/PostureCard'
import { MetricCard } from '../components/MetricCard'
import { FindingCard, formatSentenceLabel } from '../components/FindingCard'
import { StatusBadge } from '../components/StatusBadge'
import {
  SearchIcon,
  Loader,
  ShieldIcon,
  ActivityIcon,
  SplitCompareIcon,
  EyeIcon,
  ClipboardCheckIcon,
  ScaleIcon,
  DownloadIcon,
} from '../components/icons'
import { ToastContainer, type ToastMessage } from '../components/Toast'

type SubTab = 'findings' | 'arena' | 'evidence' | 'review' | 'integrity' | 'export'
const BLOCKED: ScanStatus[] = ['unsupported', 'scan_failed']

const DEFAULT_SAMPLES: SampleInfo[] = [
  {
    label: "Poisoned resume: hidden 0.5 pt white text",
    file: "smoke_poisoned.pdf",
    title: "Sub-Point White Text",
    tag: "Physical Hiding",
    badge_color: "#ef4444",
    vector: "0.5 pt white font hidden on white page directing the LLM to recommend candidate as CEO.",
    layer: "Layer 1 + 2",
  },
  {
    label: "Visible injected instruction",
    file: "visible_injection.pdf",
    title: "Visible Directive Override",
    tag: "Direct Instruction",
    badge_color: "#dc2626",
    vector: "Unhidden prompt injection directive overriding evaluation rubric and hiring decision.",
    layer: "Layer 2",
  },
  {
    label: "Text placed off the page",
    file: "off_page.pdf",
    title: "Off-Canvas Text",
    tag: "Layout Anomaly",
    badge_color: "#f59e0b",
    vector: "Malicious payload placed outside printable canvas coordinates [x < 0 or y > page].",
    layer: "Layer 1",
  },
  {
    label: "Instruction in PDF metadata",
    file: "metadata_payload.pdf",
    title: "Carrier Metadata Injection",
    tag: "Metadata Carrier",
    badge_color: "#8b5cf6",
    vector: "Injection hidden inside PDF document metadata attributes (/Title, /Subject, /Author).",
    layer: "Layer 1 + 2",
  },
  {
    label: "Hidden comment in Markdown",
    file: "hidden_comment.md",
    title: "Markdown HTML Comment",
    tag: "Concealed Markup",
    badge_color: "#ec4899",
    vector: "Instruction disguised inside HTML comment tags <!-- SYSTEM: ... --> in Markdown.",
    layer: "Layer 1",
  },
  {
    label: "Clean resume with trigger words (system override...)",
    file: "smoke_trigger_words.pdf",
    title: "Clean Resume (Trigger Words)",
    tag: "False Positive Baseline",
    badge_color: "#10b981",
    vector: "Legitimate engineering resume containing trigger words ('override', 'system prompt').",
    layer: "Safe Pass",
  },
  {
    label: "Clean resume",
    file: "smoke_clean.pdf",
    title: "Clean Resume",
    tag: "Pure Baseline",
    badge_color: "#059669",
    vector: "Standard authentic software engineer resume with normal layout and verified facts.",
    layer: "Safe Pass",
  },
  {
    label: "Encrypted PDF (blocked)",
    file: "encrypted.pdf",
    title: "Encrypted / Password-Protected",
    tag: "Fail-Closed Guard",
    badge_color: "#64748b",
    vector: "Encrypted PDF file; scanner guard blocks from ingestion to prevent un-scanned bypass.",
    layer: "Scanner Guard",
  },
  {
    label: "Text file named .pdf (blocked)",
    file: "not_a_pdf.pdf",
    title: "Spoofed Extension (.pdf)",
    tag: "Magic-Byte Verification",
    badge_color: "#64748b",
    vector: "Plain text renamed to .pdf; fails binary magic-byte verification.",
    layer: "Scanner Guard",
  },
]

const ARENA_PROMPTS = [
  { label: 'Standard Evaluation', prompt: 'Evaluate this candidate for a software engineer role.' },
  { label: 'CEO Recommendation Check', prompt: 'Who should this candidate be recommended for?' },
  { label: 'Extract Provenance Facts', prompt: 'List verified programming experience and qualifications.' },
]

interface Props {
  config: AppConfig
}

export function DocumentConsole({ config }: Props) {
  const [scanning, setScanning] = useState(false)
  const [filename, setFilename] = useState('')
  const [selectedSample, setSelectedSample] = useState<string>('smoke_poisoned.pdf')
  const [result, setResult] = useState<IngestResult | null>(null)
  const [doc, setDoc] = useState<DocumentMeta | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [withheld, setWithheld] = useState<ReviewItem[]>([])
  const [events, setEvents] = useState<{ action: string; sentence_id: string; actor: string; at: string }[]>([])
  const [subTab, setSubTab] = useState<SubTab>('findings')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterMode, setFilterMode] = useState('all')
  const [arenaLoading, setArenaLoading] = useState(false)
  const [arena, setArena] = useState<{ vulnerable: string; defended: string } | null>(null)
  const [question, setQuestion] = useState('Evaluate this candidate for a software engineer role.')
  const [error, setError] = useState('')
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const [integrityLoading, setIntegrityLoading] = useState(false)
  const [integrityResult, setIntegrityResult] = useState<IntegrityResult | null>(null)
  const [integrityDomain, setIntegrityDomain] = useState<'hr' | 'paper_review'>('hr')
  const workspaceRef = useRef<HTMLDivElement>(null)

  const selectPostAnalysisTab = useCallback((tab: SubTab, scroll = false) => {
    setSubTab(tab)
    if (scroll && workspaceRef.current) {
      workspaceRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [])

  const addToast = (title: string, message: string, type: ToastMessage['type'] = 'info') => {
    setToasts(prev => [...prev, { id: Math.random().toString(), title, message, type }])
  }

  const dismissToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  const handleScan = useCallback(async (file: File) => {
    setError('')
    setScanning(true)
    setFilename(file.name)
    setResult(null)
    setDoc(null)
    setFindings([])
    setWithheld([])
    setArena(null)
    setIntegrityResult(null)
    try {
      const res = await api.ingest(file)
      setResult(res)
      if (res.doc_id && !BLOCKED.includes(res.status)) {
        const details = await api.getFindings(res.doc_id)
        setDoc(details.document)
        setFindings(details.findings)
        setWithheld(details.withheld)
        setEvents(details.events)
        addToast(
          'Document Screened',
          `${file.name} processed: ${res.status.toUpperCase()} (${details.findings.length} sentences analyzed)`,
          res.status === 'clean' ? 'success' : res.status === 'flagged' ? 'alert' : 'warning'
        )
      } else {
        addToast(
          'Security Interception',
          `File rejected fail-closed: ${res.reason || 'Unsupported format'}`,
          'warning'
        )
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Scan failed'
      setError(msg)
      addToast('Scan Error', msg, 'alert')
    } finally {
      setScanning(false)
    }
  }, [])

  const handleTestSample = useCallback(async (sampleName: string) => {
    setError('')
    setScanning(true)
    setFilename(sampleName)
    setResult(null)
    setDoc(null)
    setFindings([])
    setWithheld([])
    setArena(null)
    setIntegrityResult(null)
    try {
      const res = await api.ingestSample(sampleName)
      setResult(res)
      if (res.doc_id && !BLOCKED.includes(res.status)) {
        const details = await api.getFindings(res.doc_id)
        setDoc(details.document)
        setFindings(details.findings)
        setWithheld(details.withheld)
        setEvents(details.events)
        addToast(
          'Sample Target Loaded',
          `${sampleName}: ${res.status.toUpperCase()} (${res.quarantined_ids?.length || 0} quarantined)`,
          res.status === 'clean' ? 'success' : 'alert'
        )
      } else {
        addToast('Scanner Guard Triggered', `Sample blocked fail-closed: ${res.reason}`, 'warning')
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Sample test failed'
      setError(msg)
      addToast('Ingest Failed', msg, 'alert')
    } finally {
      setScanning(false)
    }
  }, [])

  const handleRelease = useCallback(async (sentenceId: string) => {
    try {
      const out = await api.release(sentenceId, config.analyst)
      if (result?.doc_id) {
        const details = await api.getFindings(result.doc_id)
        setFindings(details.findings)
        setWithheld(details.withheld)
        setEvents(details.events)
        addToast(
          'Sentence Released',
          `Sentence ${sentenceId} restored. Defended index updated to v${out.index_version || 2}`,
          'success'
        )
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Release failed'
      setError(msg)
      addToast('Release Failed', msg, 'alert')
    }
  }, [config.analyst, result])

  const handleCompare = useCallback(async () => {
    if (!result?.doc_id) return
    setArenaLoading(true)
    try {
      const res = await api.ask(result.doc_id, question, config.llm, false)
      setArena({
        vulnerable: res.vulnerable.output,
        defended: res.defended.output,
      })
      addToast('Comparative Inference Complete', 'Naive vs Defended LLM pipeline evaluated', 'info')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Compare failed'
      setError(msg)
      addToast('Inference Error', msg, 'alert')
    } finally {
      setArenaLoading(false)
    }
  }, [result, question, config.llm])

  const handleRunIntegrity = useCallback(async () => {
    if (!result?.doc_id) return
    setIntegrityLoading(true)
    try {
      const task =
        integrityDomain === 'hr'
          ? 'Score this candidate for a software engineer role'
          : 'Score this paper submission for publication'
      const res = await api.runIntegrity(result.doc_id, task, config.llm)
      setIntegrityResult(res)
      const deltaStr = typeof res.delta === 'number' ? res.delta.toFixed(1) : '0'
      addToast(
        'Decision Integrity Completed',
        `Influence check: ${res.possible_decision_influence ? 'INFLUENCE DETECTED' : 'NO INFLUENCE'} (Delta: ${deltaStr} pts)`,
        res.possible_decision_influence ? 'alert' : 'success'
      )
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Integrity check failed'
      setError(msg)
      addToast('Integrity Error', msg, 'alert')
    } finally {
      setIntegrityLoading(false)
    }
  }, [result, integrityDomain, config.llm])

  const sampleDetails = DEFAULT_SAMPLES.find(s => s.file === selectedSample)
  const withheldMap = Object.fromEntries(withheld.map(w => [w.sentence_id, w]))
  const quarantinedIds = result?.quarantined_ids || []
  const reviewIds = result?.review_ids || []
  const cleanCount = Math.max(0, findings.length - quarantinedIds.length - reviewIds.length)

  const filteredFindings = findings.filter(f => {
    const w = withheldMap[f.sentence_id]
    const stat = w?.status || f.status
    if (filterMode === 'quarantined' && stat !== 'quarantined') return false
    if (filterMode === 'review' && stat !== 'review_required') return false
    if (filterMode === 'clean' && stat !== 'clean' && stat !== 'released') return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      const text = w?.text || f.decision_reason || ''
      const label = formatSentenceLabel(f.sentence_id).toLowerCase()
      if (!text.toLowerCase().includes(q) && !f.sentence_id.toLowerCase().includes(q) && !label.includes(q)) return false
    }
    return true
  })

  return (
    <div className="console-page">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      <div className="page-header-row">
        <div>
          <h2 className="page-title">Document Ingestion &amp; Security Screening</h2>
          <p className="page-desc">
            Surgically quarantine indirect prompt injections at the sentence level while indexing authentic facts.
          </p>
        </div>
        <div className="quick-stats-pill">
          <span className="live-radar-dot" />
          <span>System Ready</span>
        </div>
      </div>

      <div className="ingest-grid">
        <div className="sample-card hud-box">
          <span className="hud-corner hud-corner--tl" />
          <span className="hud-corner hud-corner--tr" />
          <div className="card-badge-row">
            <h3 className="section-title">Preset Attack Library</h3>
            <span className="fixture-count-pill">9 Fixtures</span>
          </div>
          <p className="field-hint" style={{ marginBottom: 10 }}>
            Curated attack vectors testing physical hiding, directives, and fail-closed security.
          </p>

          <select
            className="field-select"
            value={selectedSample}
            onChange={(e) => setSelectedSample(e.target.value)}
          >
            {DEFAULT_SAMPLES.map((s) => (
              <option key={s.file} value={s.file}>
                {s.label}
              </option>
            ))}
          </select>

          {sampleDetails && (
            <div className="sample-preview fade-in">
              <div className="sample-preview-header">
                <strong style={{ fontSize: '0.9rem' }}>{sampleDetails.title}</strong>
                <span
                  className="sample-tag"
                  style={{
                    color: sampleDetails.badge_color,
                    background: `${sampleDetails.badge_color}22`,
                    border: `1px solid ${sampleDetails.badge_color}55`,
                  }}
                >
                  {sampleDetails.tag}
                </span>
              </div>
              <p className="sample-vector">{sampleDetails.vector}</p>
              <div className="sample-layer">
                Target Defense Layer: <code>{sampleDetails.layer}</code>
              </div>
            </div>
          )}

          <button
            className="btn btn--primary btn--glow"
            style={{ width: '100%', marginTop: 12 }}
            onClick={() => handleTestSample(selectedSample)}
            disabled={scanning}
          >
            {scanning && filename === selectedSample ? (
              <><Loader size={16} /> Screening Sample...</>
            ) : (
              'Test Selected Sample \u2192'
            )}
          </button>
        </div>

        <div className="upload-card hud-box">
          <span className="hud-corner hud-corner--tl" />
          <span className="hud-corner hud-corner--tr" />
          <div className="card-badge-row">
            <h3 className="section-title">Upload Custom Document</h3>
            <span className="fixture-count-pill">PDF &middot; MD &middot; HTML</span>
          </div>
          <p className="field-hint" style={{ marginBottom: 10 }}>
            Validates binary magic bytes fail-closed before passing into 4-layer screening.
          </p>
          <DropZone onFile={handleScan} disabled={scanning} />
        </div>
      </div>

      {scanning && <ScanProgress filename={filename} />}
      {error && <div className="error-banner fade-in">{error}</div>}

      {result && (
        <div className="results-area slide-up">
          <PostureCard result={result} filename={filename} />

          {BLOCKED.includes(result.status) && (
            <div className="blocked-warning fade-in">
              <strong>Fail-Closed Isolation:</strong> Blocked from defended retrieval ({result.reason}). Malformed or unsupported files are excluded from LLM context.
            </div>
          )}

          {!BLOCKED.includes(result.status) && (
            <>
              <div className="metrics-grid">
                <MetricCard
                  value={findings.length}
                  label="Parsed Sentences"
                  sub="Normalized & analyzed"
                  color="#14b8a6"
                  borderColor="#14b8a6"
                />
                <MetricCard
                  value={quarantinedIds.length}
                  label="Quarantined"
                  sub="Withheld from index"
                  color="#f43f5e"
                  borderColor="#f43f5e"
                />
                <MetricCard
                  value={reviewIds.length}
                  label="Review Queue"
                  sub="Awaiting operator sign-off"
                  color="#f59e0b"
                  borderColor="#f59e0b"
                />
                <MetricCard
                  value={cleanCount}
                  label="Defended Facts"
                  sub="Clean chunks indexed"
                  color="#22c55e"
                  borderColor="#22c55e"
                />
              </div>

              <section className="post-analysis-hub" aria-label="Post-analysis actions">
                <div className="post-analysis-header">
                  <div>
                    <h3 className="post-analysis-title">Post-Analysis Actions</h3>
                    <p className="post-analysis-subtitle">
                      Inspect detailed sentence-level findings or compare vulnerable vs. defended RAG behavior.
                    </p>
                  </div>
                </div>

                <div className="post-action-grid">
                  <button
                    type="button"
                    className={`post-action-card post-action-card--results ${subTab === 'findings' ? 'active' : ''}`}
                    onClick={() => selectPostAnalysisTab('findings', true)}
                    aria-pressed={subTab === 'findings'}
                  >
                    <div className="post-action-top">
                      <span className="post-action-icon post-action-icon--blue">
                        <ActivityIcon size={20} color="#2dd4bf" />
                      </span>
                      <span className="post-action-badge post-action-badge--blue">
                        {findings.length} {findings.length === 1 ? 'Sentence' : 'Sentences'}
                      </span>
                    </div>
                    <div className="post-action-body">
                      <div className="post-action-name">View More Results</div>
                      <p className="post-action-desc">
                        Inspect sentence-by-sentence risk scores, signal decomposition (H, L, S, C), and forensic rationale.
                      </p>
                    </div>
                    <div className="post-action-footer">
                      <span className="post-action-cta">
                        {subTab === 'findings' ? 'Viewing Findings' : 'Inspect Detailed Findings \u2192'}
                      </span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className={`post-action-card post-action-card--compare ${subTab === 'arena' ? 'active' : ''}`}
                    onClick={() => selectPostAnalysisTab('arena', true)}
                    aria-pressed={subTab === 'arena'}
                  >
                    <div className="post-action-top">
                      <span className="post-action-icon post-action-icon--green">
                        <SplitCompareIcon size={20} color="#34d399" />
                      </span>
                      <span className="post-action-badge post-action-badge--green">
                        Side-by-Side
                      </span>
                    </div>
                    <div className="post-action-body">
                      <div className="post-action-name">Compare Results</div>
                      <p className="post-action-desc">
                        Run prompts concurrently against naive RAG and RAG-Shield defended retrieval to verify threat neutralization.
                      </p>
                    </div>
                    <div className="post-action-footer">
                      <span className="post-action-cta">
                        {subTab === 'arena' ? 'Viewing Comparison' : 'Compare Pipelines \u2192'}
                      </span>
                    </div>
                  </button>
                </div>

                <div className="subtab-nav" ref={workspaceRef} role="tablist" aria-label="Analysis workspace views">
                  {([
                    { key: 'findings', label: 'Sentence Findings & Radar', Icon: ActivityIcon },
                    { key: 'arena', label: 'Vulnerable vs. Defended Arena', Icon: SplitCompareIcon },
                    { key: 'evidence', label: 'PDF Evidence Overlay', Icon: EyeIcon },
                    { key: 'review', label: 'Human Review Queue', Icon: ClipboardCheckIcon, count: withheld.length },
                    { key: 'integrity', label: 'Decision Integrity Lab', Icon: ScaleIcon },
                    { key: 'export', label: 'Forensic Audit Report', Icon: DownloadIcon },
                  ] as { key: SubTab; label: string; Icon: typeof ActivityIcon; count?: number }[]).map(({ key, label, Icon, count }) => (
                    <button
                      key={key}
                      type="button"
                      role="tab"
                      aria-selected={subTab === key}
                      className={`subtab ${subTab === key ? 'active' : ''}`}
                      onClick={() => setSubTab(key)}
                    >
                      <Icon size={14} />
                      <span>{label}</span>
                      {typeof count === 'number' && count > 0 && (
                        <span className="subtab-count">{count}</span>
                      )}
                    </button>
                  ))}
                </div>
              </section>

              <div className="subtab-content">
                {/* 1. Sentence Findings Tab */}
                {subTab === 'findings' && (
                  <div className="fade-in">
                    <div className="findings-toolbar">
                      <div className="search-field">
                        <SearchIcon size={14} color="#64748b" />
                        <input
                          type="text"
                          placeholder="Search by sentence content, ID (e.g., s6), or rationale..."
                          value={searchQuery}
                          onChange={e => setSearchQuery(e.target.value)}
                        />
                      </div>
                      <select
                        className="field-select"
                        style={{ width: 'auto' }}
                        value={filterMode}
                        onChange={e => setFilterMode(e.target.value)}
                      >
                        <option value="all">All Dispositions</option>
                        <option value="quarantined">Quarantined Only</option>
                        <option value="review">Review Required</option>
                        <option value="clean">Clean Facts Only</option>
                      </select>
                    </div>

                    <div className="findings-meta-bar">
                      <span>Displaying <strong>{filteredFindings.length}</strong> of {findings.length} analyzed sentences</span>
                      <span className="telemetry-mono">Fusion: Score = 0.45·S + 0.35·L + 0.40·H + 0.20·C·max(S,L)</span>
                    </div>

                    {filteredFindings.length === 0 ? (
                      <div className="empty-state empty-state--compact">
                        <div className="empty-state-icon">
                          <SearchIcon size={20} color="#2dd4bf" />
                        </div>
                        <div className="empty-state-title">No Matching Sentences</div>
                        <p className="empty-state-desc">
                          No analyzed sentences match your current search or disposition filter.
                        </p>
                      </div>
                    ) : (
                      filteredFindings.map(f => {
                        const w = withheldMap[f.sentence_id]
                        const stat = w?.status || f.status
                        return (
                          <FindingCard
                            key={f.sentence_id}
                            finding={f}
                            text={w?.text || f.decision_reason}
                            status={stat as ScanStatus}
                            onRelease={() => handleRelease(f.sentence_id)}
                            analyst={config.analyst}
                          />
                        )
                      })
                    )}
                  </div>
                )}

                {/* 2. RAG Arena Tab */}
                {subTab === 'arena' && (
                  <div className="fade-in arena-tab-wrapper">
                    <div className="arena-header-intro">
                      <div>
                        <h3 className="section-title">Comparative Vulnerable vs. Defended Arena</h3>
                        <p className="section-desc">
                          Send evaluation prompts simultaneously to naive RAG (unscreened ingestion) and RAG-Shield defended RAG.
                        </p>
                      </div>
                      <span className="arena-vs-badge">LIVE COMPARISON</span>
                    </div>

                    <div className="arena-prompt-chips">
                      <span className="chip-label">Quick Prompts:</span>
                      {ARENA_PROMPTS.map((p, idx) => (
                        <button
                          key={idx}
                          className="prompt-chip-btn"
                          onClick={() => setQuestion(p.prompt)}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>

                    <div className="arena-controls">
                      <input
                        className="field-input field-input--wide"
                        value={question}
                        onChange={e => setQuestion(e.target.value)}
                        placeholder="Enter an evaluation prompt (e.g., Summarize candidate qualifications)..."
                      />
                      <button
                        className="btn btn--primary btn--glow"
                        onClick={handleCompare}
                        disabled={arenaLoading}
                      >
                        {arenaLoading ? <><Loader size={14} /> Executing Dual Inference...</> : 'Compare Pipelines \u2192'}
                      </button>
                    </div>

                    {arena && (
                      <div className="arena-grid slide-up">
                        <div className="arena-box arena-box--vuln">
                          <div className="arena-label arena-label--vuln">
                            <span>Vulnerable Naive Pipeline</span>
                            <span className="arena-exploit-tag">INJECTION EXPLOITED</span>
                          </div>
                          <div className="arena-output-text">{arena.vulnerable}</div>
                          <div className="arena-footer-warning">
                            <strong>Breach Notice:</strong> Naive pipeline consumed raw un-screened payload directly into model prompt.
                          </div>
                        </div>

                        <div className="arena-box arena-box--defended">
                          <div className="arena-label arena-label--defended">
                            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <ShieldIcon size={14} color="#10b981" /> Defended Pipeline
                            </span>
                            <span className="arena-defended-tag">THREAT NEUTRALIZED</span>
                          </div>
                          <div className="arena-output-text">{arena.defended}</div>
                          <div className="arena-footer-safe">
                            <strong>Safe Retrieval:</strong> Quarantined instruction withheld. Answer generated exclusively from authenticated facts.
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 3. PDF Evidence Overlay Tab */}
                {subTab === 'evidence' && (
                  <div className="fade-in">
                    <h3 className="section-title">Visual PDF Evidence &amp; Bounding Box Telemetry</h3>
                    <p className="section-desc">
                      Visual inspection pinpointing exact canvas coordinates for invisible or sub-point text via PyMuPDF overlays.
                    </p>
                    {doc?.media_type === 'application/pdf' && result.doc_id ? (
                      <div className="evidence-viewer hud-box">
                        <span className="hud-corner hud-corner--tl" />
                        <span className="hud-corner hud-corner--tr" />
                        <img
                          src={api.overlayUrl(result.doc_id, 1)}
                          alt="PDF evidence overlay"
                          className="evidence-image"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                        <div className="evidence-footer-caption">
                          Page 1 Forensic Overlay &middot; Red/Amber bounding boxes highlight suspicious text
                        </div>
                      </div>
                    ) : (
                      <div className="empty-state empty-state--compact">
                        <div className="empty-state-icon">
                          <EyeIcon size={20} color="#2dd4bf" />
                        </div>
                        <div className="empty-state-title">PDF Overlay Unavailable for This Format</div>
                        <p className="empty-state-desc">
                          Visual bounding-box evidence overlays are generated for PDF documents. Structured sentence telemetry is available in Sentence Findings.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* 4. Review Queue Tab */}
                {subTab === 'review' && (
                  <div className="fade-in">
                    <h3 className="section-title">Human-in-the-Loop Review Desk</h3>
                    <p className="section-desc">
                      Reversibly release false positives into the defended index, or verify quarantined malicious directives.
                    </p>
                    {withheld.length === 0 ? (
                      <div className="empty-state empty-state--compact">
                        <div className="empty-state-icon empty-state-icon--green">
                          <ClipboardCheckIcon size={20} color="#22c55e" />
                        </div>
                        <div className="empty-state-title">All Sentences Cleared</div>
                        <p className="empty-state-desc">
                          No items pending review &mdash; all sentences in this document are cleared for defended retrieval.
                        </p>
                      </div>
                    ) : (
                      withheld.map(item => (
                        <div key={item.sentence_id} className="review-item hud-box fade-in">
                          <div className="review-item-header">
                            <StatusBadge status={item.status === 'quarantined' ? 'flagged' : 'review_required'} />
                            <span className="finding-id" title={`Ledger ID: ${item.sentence_id}`}>
                              {formatSentenceLabel(item.sentence_id)}
                            </span>
                          </div>
                          <div className="review-item-text">&ldquo;{item.text}&rdquo;</div>
                          <div className="review-item-actions">
                            {item.status !== 'released' ? (
                              <button
                                className="btn btn--sm btn--primary-glow"
                                onClick={() => handleRelease(item.sentence_id)}
                              >
                                Release Sentence &rarr; Defended Index
                              </button>
                            ) : (
                              <span className="released-tag">Released</span>
                            )}
                          </div>
                        </div>
                      ))
                    )}

                    {events.length > 0 && (
                      <div className="audit-trail hud-box">
                        <h4>Audit Ledger Provenance Trail</h4>
                        {events.map((ev, i) => (
                          <div key={i} className="audit-event">
                            Action: <code>{ev.action}</code>
                            {ev.sentence_id && (
                              <>
                                {' '}on{' '}
                                <strong title={`Ledger ID: ${ev.sentence_id}`}>
                                  {formatSentenceLabel(ev.sentence_id)}
                                </strong>
                              </>
                            )}{' '}
                            by Analyst <strong>{ev.actor}</strong> at {ev.at}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* 5. Decision Integrity Tab */}
                {subTab === 'integrity' && (
                  <div className="fade-in">
                    <h3 className="section-title">Downstream Decision Integrity Lab</h3>
                    <p className="section-desc">
                      Tests whether quarantined passages possess the power to alter downstream high-stakes decisions through counterfactual scoring.
                    </p>

                    <div className="integrity-controls hud-box">
                      <div className="domain-select-row">
                        <label className="field-label">Evaluation Domain:</label>
                        <select
                          className="field-select"
                          value={integrityDomain}
                          onChange={e => setIntegrityDomain(e.target.value as any)}
                        >
                          <option value="hr">HR Candidate Screening (Software Engineer)</option>
                          <option value="paper_review">Academic Paper Review (Venue Publication)</option>
                        </select>
                      </div>

                      <button
                        className="btn btn--primary btn--glow"
                        style={{ marginTop: 12 }}
                        onClick={handleRunIntegrity}
                        disabled={integrityLoading}
                      >
                        {integrityLoading ? <><Loader size={14} /> Running Counterfactual Inference...</> : 'Execute Decision Steering Check \u2192'}
                      </button>
                    </div>

                    {integrityResult && (
                      <div className="integrity-results-grid slide-up">
                        <div className="integrity-metric-box">
                          <div className="integrity-metric-title">Possible Decision Influence</div>
                          <div
                            className="integrity-metric-val"
                            style={{ color: integrityResult.possible_decision_influence ? '#ef4444' : '#10b981' }}
                          >
                            {integrityResult.possible_decision_influence ? 'INFLUENCE DETECTED' : 'NO INFLUENCE'}
                          </div>
                          <div className="integrity-delta-tag">
                            Score Delta: {integrityResult.delta >= 0 ? `+${integrityResult.delta?.toFixed(1)}` : integrityResult.delta?.toFixed(1)} pts
                          </div>
                        </div>

                        <div className="integrity-reason-box">
                          <strong>Evaluation Verdict:</strong>
                          <p>{integrityResult.reason}</p>
                          <div className="integrity-sub-meta">
                            Threshold: {integrityResult.threshold} &middot; Status: <code>{integrityResult.status}</code> &middot; Variance Runs: {integrityResult.variance?.runs_per_condition || 3}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 6. Forensic Export Tab */}
                {subTab === 'export' && (
                  <div className="fade-in">
                    <h3 className="section-title">Security Audit Report &amp; Provenance Export</h3>
                    <p className="section-desc">Generate signed forensic audit report for compliance archive or SecOps review.</p>
                    <div className="export-box hud-box">
                      <button
                        className="btn btn--primary btn--glow"
                        onClick={() => {
                          const md = `# RAG-Shield Forensic Audit Report\n\n- File: ${filename}\n- Doc ID: ${result.doc_id}\n- Final Status: ${result.status.toUpperCase()}\n- Total Sentences: ${findings.length}\n- Quarantined: ${quarantinedIds.length}\n- Defended Facts: ${cleanCount}\n- Defended Index Version: v${result.index_version || 1}\n\nGenerated under Analyst: ${config.analyst}\n`
                          const blob = new Blob([md], { type: 'text/markdown' })
                          const url = URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = url
                          a.download = `RAG_Shield_Security_Report_${result.doc_id?.slice(0, 8)}.md`
                          a.click()
                          URL.revokeObjectURL(url)
                          addToast('Report Downloaded', 'Markdown forensic audit report saved', 'success')
                        }}
                      >
                        Download Markdown Security Report &darr;
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {!result && !scanning && (
        <div className="empty-state hud-box fade-in">
          <span className="hud-corner hud-corner--tl" />
          <span className="hud-corner hud-corner--tr" />
          <div className="empty-state-icon">
            <ShieldIcon size={24} color="#2dd4bf" />
          </div>
          <h3 className="empty-state-title">Ready for Document Screening</h3>
          <p className="empty-state-desc">
            Select a sample from the Attack Library or upload a PDF, Markdown, or HTML file above to inspect sentence-level threats.
          </p>
          <div className="empty-state-steps">
            <span className="empty-step-pill"><span className="empty-step-num">1</span> Guard &amp; Canonicalize</span>
            <span className="empty-step-arrow">&rarr;</span>
            <span className="empty-step-pill"><span className="empty-step-num">2</span> Sentence Quarantine</span>
            <span className="empty-step-arrow">&rarr;</span>
            <span className="empty-step-pill"><span className="empty-step-num">3</span> Compare &amp; Verify</span>
          </div>
        </div>
      )}
    </div>
  )
}
