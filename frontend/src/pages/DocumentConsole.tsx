import { useState, useCallback } from 'react'
import type { AppConfig, IngestResult, Finding, ReviewItem, DocumentMeta, ScanStatus, SampleInfo } from '../types'
import * as api from '../api'
import { DropZone } from '../components/DropZone'
import { ScanProgress } from '../components/ScanProgress'
import { PostureCard } from '../components/PostureCard'
import { MetricCard } from '../components/MetricCard'
import { FindingCard } from '../components/FindingCard'
import { StatusBadge } from '../components/StatusBadge'
import { SearchIcon, Loader } from '../components/icons'

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

  const handleScan = useCallback(async (file: File) => {
    setError('')
    setScanning(true)
    setFilename(file.name)
    setResult(null)
    setDoc(null)
    setFindings([])
    setWithheld([])
    setArena(null)
    try {
      const res = await api.ingest(file)
      setResult(res)
      if (res.doc_id && !BLOCKED.includes(res.status)) {
        const details = await api.getFindings(res.doc_id)
        setDoc(details.document)
        setFindings(details.findings)
        setWithheld(details.withheld)
        setEvents(details.events)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Scan failed')
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
    try {
      const res = await api.ingestSample(sampleName)
      setResult(res)
      if (res.doc_id && !BLOCKED.includes(res.status)) {
        const details = await api.getFindings(res.doc_id)
        setDoc(details.document)
        setFindings(details.findings)
        setWithheld(details.withheld)
        setEvents(details.events)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Sample test failed')
    } finally {
      setScanning(false)
    }
  }, [])

  const handleRelease = useCallback(async (sentenceId: string) => {
    try {
      await api.release(sentenceId, config.analyst)
      if (result?.doc_id) {
        const details = await api.getFindings(result.doc_id)
        setFindings(details.findings)
        setWithheld(details.withheld)
        setEvents(details.events)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Release failed')
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Compare failed')
    } finally {
      setArenaLoading(false)
    }
  }, [result, question, config.llm])

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
      const text = w?.text || f.decision_reason
      if (!text.toLowerCase().includes(q) && !f.sentence_id.toLowerCase().includes(q)) return false
    }
    return true
  })

  return (
    <div className="console-page">
      <h2 className="page-title">Document Ingestion &amp; Screening</h2>

      <div className="ingest-grid">
        <div className="sample-card">
          <h3 className="section-title">Preset Attack Fixture</h3>
          <p className="field-hint" style={{ marginBottom: 8 }}>
            Pre-configured attack samples verifying physical hiding, directives, and fail-closed guards.
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
            <div className="sample-preview">
              <div className="sample-preview-header">
                <strong>{sampleDetails.title}</strong>
                <span
                  className="sample-tag"
                  style={{
                    color: sampleDetails.badge_color,
                    background: `${sampleDetails.badge_color}22`,
                    border: `1px solid ${sampleDetails.badge_color}44`,
                  }}
                >
                  {sampleDetails.tag}
                </span>
              </div>
              <p className="sample-vector">{sampleDetails.vector}</p>
              <div className="sample-layer">Target Defense: <code>{sampleDetails.layer}</code></div>
            </div>
          )}
          <button
            className="btn btn--primary"
            style={{ width: '100%', marginTop: 10 }}
            onClick={() => handleTestSample(selectedSample)}
            disabled={scanning}
          >
            Test Selected Sample
          </button>
        </div>

        <div className="upload-card">
          <h3 className="section-title">Upload Custom Document</h3>
          <p className="field-hint" style={{ marginBottom: 8 }}>
            Accepts PDF, Markdown (.md), and HTML. Binary magic-bytes validated fail-closed.
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
              Blocked from defended retrieval: {result.reason}. Fail-closed security enforced.
            </div>
          )}

          {!BLOCKED.includes(result.status) && (
            <>
              <div className="metrics-grid">
                <MetricCard value={findings.length} label="Parsed Sentences" sub="Normalized & analyzed" />
                <MetricCard value={quarantinedIds.length} label="Quarantined" sub="Withheld from index" color="#ef4444" borderColor="#ef4444" />
                <MetricCard value={reviewIds.length} label="Review Queue" sub="Awaiting operator sign-off" color="#f59e0b" borderColor="#f59e0b" />
                <MetricCard value={cleanCount} label="Defended Facts" sub="Clean chunks indexed" color="#10b981" borderColor="#10b981" />
              </div>

              <div className="subtab-nav">
                {([
                  ['findings', 'Sentence Findings'],
                  ['arena', 'RAG Arena'],
                  ['evidence', 'PDF Evidence'],
                  ['review', 'Review Queue'],
                  ['integrity', 'Integrity Lab'],
                  ['export', 'Audit Export'],
                ] as [SubTab, string][]).map(([key, label]) => (
                  <button key={key} className={`subtab ${subTab === key ? 'active' : ''}`} onClick={() => setSubTab(key)}>
                    {label}
                  </button>
                ))}
              </div>

              <div className="subtab-content">
                {subTab === 'findings' && (
                  <div className="fade-in">
                    <div className="findings-toolbar">
                      <div className="search-field">
                        <SearchIcon size={14} color="#64748b" />
                        <input type="text" placeholder="Search sentence text or ID..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
                      </div>
                      <select className="field-select" value={filterMode} onChange={e => setFilterMode(e.target.value)}>
                        <option value="all">All Sentences</option>
                        <option value="quarantined">Quarantined Only</option>
                        <option value="review">Review Required</option>
                        <option value="clean">Clean Only</option>
                      </select>
                    </div>
                    <p className="findings-count">Displaying {filteredFindings.length} of {findings.length} sentences</p>
                    {filteredFindings.length === 0 ? (
                      <div className="empty-state">No sentences match the current filter.</div>
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

                {subTab === 'arena' && (
                  <div className="fade-in">
                    <h3 className="section-title">Vulnerable vs. Defended RAG</h3>
                    <div className="arena-controls">
                      <input className="field-input field-input--wide" value={question} onChange={e => setQuestion(e.target.value)} placeholder="Evaluation prompt..." />
                      <button className="btn btn--primary" onClick={handleCompare} disabled={arenaLoading}>
                        {arenaLoading ? <><Loader size={14} /> Comparing...</> : 'Compare Pipelines'}
                      </button>
                    </div>
                    {arena && (
                      <div className="arena-grid slide-up">
                        <div className="arena-box arena-box--vuln">
                          <div className="arena-label arena-label--vuln">Vulnerable Pipeline</div>
                          <div className="arena-output">{arena.vulnerable}</div>
                          <div className="arena-warning">Consumes raw document text directly.</div>
                        </div>
                        <div className="arena-box arena-box--defended">
                          <div className="arena-label arena-label--defended">Defended Pipeline</div>
                          <div className="arena-output">{arena.defended}</div>
                          <div className="arena-safe">Filtered through 4-Layer Security Middleware.</div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {subTab === 'evidence' && (
                  <div className="fade-in">
                    <h3 className="section-title">Visual PDF Evidence Overlay</h3>
                    {doc?.media_type === 'application/pdf' && result.doc_id ? (
                      <div className="evidence-viewer">
                        <img src={api.overlayUrl(result.doc_id, 1)} alt="PDF evidence overlay" className="evidence-image"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      </div>
                    ) : (
                      <div className="empty-state">Visual evidence overlays are available for PDF documents.</div>
                    )}
                  </div>
                )}

                {subTab === 'review' && (
                  <div className="fade-in">
                    <h3 className="section-title">Review Queue</h3>
                    {withheld.length === 0 ? (
                      <div className="empty-state">No items pending review.</div>
                    ) : (
                      withheld.map(item => (
                        <div key={item.sentence_id} className="review-item fade-in">
                          <div className="review-item-header">
                            <StatusBadge status={item.status === 'quarantined' ? 'flagged' : 'review_required'} />
                            <code>{item.sentence_id}</code>
                          </div>
                          <div className="review-item-text">{item.text}</div>
                          <div className="review-item-actions">
                            {item.status !== 'released' && (
                              <button className="btn btn--sm btn--outline" onClick={() => handleRelease(item.sentence_id)}>Release</button>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                    {events.length > 0 && (
                      <div className="audit-trail">
                        <h4>Audit Ledger</h4>
                        {events.map((ev, i) => (
                          <div key={i} className="audit-event">
                            <code>{ev.action}</code> on <code>{ev.sentence_id}</code> by {ev.actor} at {ev.at}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {subTab === 'integrity' && (
                  <div className="fade-in">
                    <h3 className="section-title">Decision Integrity Lab</h3>
                    <p className="section-desc">
                      Tests whether quarantined sentences can alter downstream high-stakes decisions
                      using counterfactual scoring with benign-removal negative controls.
                    </p>
                    <div className="empty-state">Enable the integrity check to run counterfactual analysis. Requires an active LLM connection.</div>
                  </div>
                )}

                {subTab === 'export' && (
                  <div className="fade-in">
                    <h3 className="section-title">Security Audit Report</h3>
                    <button className="btn btn--primary" onClick={() => {
                      const md = `# RAG-Shield Audit Report\n\nDocument: ${filename}\nDoc ID: ${result.doc_id}\nStatus: ${result.status}\nSentences: ${findings.length}\nQuarantined: ${quarantinedIds.length}\nReview: ${reviewIds.length}\nClean: ${cleanCount}`
                      const blob = new Blob([md], { type: 'text/markdown' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url; a.download = `RAG_Shield_Report_${result.doc_id?.slice(0, 8)}.md`
                      a.click(); URL.revokeObjectURL(url)
                    }}>
                      Download Markdown Report
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {!result && !scanning && (
        <div className="empty-state fade-in">Upload a document or choose a preset attack sample to begin security screening.</div>
      )}
    </div>
  )
}
