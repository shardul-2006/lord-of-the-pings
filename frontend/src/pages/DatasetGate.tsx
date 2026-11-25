import { useState, useCallback } from 'react'
import type { AppConfig, DatasetResult } from '../types'
import * as api from '../api'
import { DropZone } from '../components/DropZone'
import { ScanProgress } from '../components/ScanProgress'
import { MetricCard } from '../components/MetricCard'
import { ToastContainer, type ToastMessage } from '../components/Toast'

interface Props {
  config: AppConfig
}

export function DatasetGate({ config: _config }: Props) {
  const [scanning, setScanning] = useState(false)
  const [filename, setFilename] = useState('')
  const [result, setResult] = useState<DatasetResult | null>(null)
  const [error, setError] = useState('')
  const [toasts, setToasts] = useState<ToastMessage[]>([])

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
    try {
      const res = await api.screenDataset(file)
      setResult(res)
      addToast(
        'Dataset Screening Complete',
        `${res.summary.total} rows analyzed: ${res.summary.quarantined} poisoned rows isolated.`,
        res.summary.quarantined > 0 ? 'alert' : 'success'
      )
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Dataset screening failed'
      setError(msg)
      addToast('Screening Error', msg, 'alert')
    } finally {
      setScanning(false)
    }
  }, [])

  const handleTestDemo = useCallback(async () => {
    setError('')
    setScanning(true)
    setFilename('poisoned.jsonl (1,000 synthetic rows)')
    setResult(null)
    try {
      const res = await api.screenDemoDataset()
      setResult(res)
      addToast(
        'Demo Dataset Screened',
        `1,000 rows screened: ${res.summary.quarantined} backdoors isolated (${res.summary.duplicates} duplicates, ${res.summary.near_duplicates} near-duplicates).`,
        'alert'
      )
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Demo dataset screening failed'
      setError(msg)
      addToast('Demo Error', msg, 'alert')
    } finally {
      setScanning(false)
    }
  }, [])

  const downloadFile = (data: unknown, name: string) => {
    const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
    const blob = new Blob([text], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
    addToast('Download Started', `Saved ${name}`, 'success')
  }

  return (
    <div className="console-page">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      <div className="page-header-row">
        <div>
          <h2 className="page-title">Pre-Retrieval Dataset Gate &amp; Backdoor Quarantine</h2>
          <p className="page-desc">
            Screen pre-retrieval corpora and fine-tuning datasets for backdoor triggers and poisoned text before vector embedding.
          </p>
        </div>
        <div className="quick-stats-pill">
          <span className="live-radar-dot" />
          <span>DATASET GATE ACTIVE</span>
        </div>
      </div>

      <div className="ingest-grid">
        <div className="sample-card hud-box">
          <span className="hud-corner hud-corner--tl" />
          <span className="hud-corner hud-corner--tr" />
          <div className="card-badge-row">
            <h3 className="section-title">Pre-Configured Poisoned Demo</h3>
            <span className="fixture-count-pill">1,000 Rows</span>
          </div>
          <p className="field-hint" style={{ marginBottom: 12 }}>
            Planted backdoor trigger tokens, exact SHA-256 duplicates, and MinHash near-duplicates.
          </p>
          <div className="sample-preview" style={{ marginBottom: 16 }}>
            <div className="sample-preview-header">
              <strong>Synthetic Backdoor Corpus</strong>
              <span className="sample-tag" style={{ color: '#ef4444', background: '#ef444422', border: '1px solid #ef444455' }}>
                100% Deterministic Test
              </span>
            </div>
            <p className="sample-vector">
              Detects rare backdoor triggers correlated with abnormal classification disagreement.
            </p>
            <div className="sample-layer">Screening Mode: <code>Batch Pre-Retrieval Gate</code></div>
          </div>
          <button
            className="btn btn--primary btn--glow"
            style={{ width: '100%' }}
            onClick={handleTestDemo}
            disabled={scanning}
          >
            {scanning ? 'Analyzing 1,000 Synthetic Rows...' : 'Test 1,000-Row Planted Demo \u2192'}
          </button>
        </div>

        <div className="upload-card hud-box">
          <span className="hud-corner hud-corner--tl" />
          <span className="hud-corner hud-corner--tr" />
          <div className="card-badge-row">
            <h3 className="section-title">Upload Custom Corpus</h3>
            <span className="fixture-count-pill">CSV &middot; JSONL</span>
          </div>
          <p className="field-hint" style={{ marginBottom: 12 }}>
            Upload fine-tuning or pre-retrieval corpus containing a &apos;text&apos; column.
          </p>
          <DropZone onFile={handleScan} disabled={scanning} accept=".csv,.jsonl" maxSizeMB={200} />
        </div>
      </div>

      {scanning && <ScanProgress filename={filename} stage="Screening dataset rows for backdoor triggers &amp; duplicates..." />}
      {error && <div className="error-banner fade-in">{error}</div>}

      {result && result.summary.status === 'completed' && (
        <div className="results-area slide-up">
          <div className="metrics-grid">
            <MetricCard
              value={result.summary.total}
              label="Total Rows"
              sub="Parsed & analyzed"
              color="#3b82f6"
              borderColor="#3b82f6"
            />
            <MetricCard
              value={result.summary.quarantined}
              label="Poisoned Rows"
              sub="Backdoor triggers isolated"
              color="#ef4444"
              borderColor="#ef4444"
            />
            <MetricCard
              value={result.summary.duplicates}
              label="Exact Duplicates"
              sub="SHA-256 deduplicated"
              color="#f59e0b"
              borderColor="#f59e0b"
            />
            <MetricCard
              value={result.summary.near_duplicates}
              label="Near Duplicates"
              sub="MinHash / LSH similarity"
              color="#8b5cf6"
              borderColor="#8b5cf6"
            />
          </div>

          {result.summary.trigger_tokens.length > 0 && (
            <div className="dataset-section hud-box fade-in">
              <span className="hud-corner hud-corner--tl" />
              <span className="hud-corner hud-corner--tr" />
              <h3 className="section-title" style={{ color: '#ef4444' }}>
                Suspicious Backdoor Trigger Tokens Detected
              </h3>
              <p className="field-hint" style={{ marginBottom: 12 }}>
                Tokens exhibiting abnormal correlation with model disagreement during masked inference.
              </p>
              <div className="token-list">
                {result.summary.trigger_tokens.map(t => (
                  <code key={t} className="trigger-token">{t}</code>
                ))}
              </div>
            </div>
          )}

          <div className="download-grid">
            <button className="btn btn--primary btn--glow" onClick={() => downloadFile(result.report, 'report.json')}>
              Download report.json (Full Telemetry) &darr;
            </button>
            <button className="btn btn--outline" onClick={() => downloadFile(result.screened, 'screened.jsonl')}>
              Download screened.jsonl (Clean Corpus) &darr;
            </button>
            <button className="btn btn--outline" style={{ borderColor: '#ef4444', color: '#fca5a5' }} onClick={() => downloadFile(result.quarantined, 'quarantined.jsonl')}>
              Download quarantined.jsonl (Poison Rows) &darr;
            </button>
          </div>
        </div>
      )}

      {result && result.summary.status !== 'completed' && (
        <div className="error-banner fade-in">Dataset could not be screened: {result.summary.reason}</div>
      )}

      {!result && !scanning && (
        <div className="empty-state fade-in">Upload a CSV or JSONL dataset or run the 1,000-row demo to inspect pre-retrieval screening.</div>
      )}
    </div>
  )
}
