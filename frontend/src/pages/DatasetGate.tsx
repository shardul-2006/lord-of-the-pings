import { useState, useCallback } from 'react'
import type { AppConfig, DatasetResult } from '../types'
import * as api from '../api'
import { DropZone } from '../components/DropZone'
import { ScanProgress } from '../components/ScanProgress'
import { MetricCard } from '../components/MetricCard'

interface Props {
  config: AppConfig
}

export function DatasetGate({ config: _config }: Props) {
  const [scanning, setScanning] = useState(false)
  const [filename, setFilename] = useState('')
  const [result, setResult] = useState<DatasetResult | null>(null)
  const [error, setError] = useState('')

  const handleScan = useCallback(async (file: File) => {
    setError('')
    setScanning(true)
    setFilename(file.name)
    setResult(null)
    try {
      const res = await api.screenDataset(file)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Dataset screening failed')
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Demo dataset screening failed')
    } finally {
      setScanning(false)
    }
  }, [])

  const downloadFile = (data: unknown, name: string) => {
    const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
    const blob = new Blob([text], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = name; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="console-page">
      <h2 className="page-title">Pre-Retrieval Dataset Gate &amp; Poison Quarantine</h2>
      <p className="page-desc">
        Screen CSV/JSONL datasets for backdoor triggers, rare token anomalies,
        and near-duplicate injections before vector indexing.
      </p>

      <div className="ingest-grid">
        <div className="sample-card">
          <h3 className="section-title">Pre-Configured Poisoned Demo</h3>
          <p className="field-hint" style={{ marginBottom: 12 }}>
            1,000 synthetic rows with planted backdoor triggers and poisoned text.
          </p>
          <div className="sample-preview" style={{ marginBottom: 16 }}>
            <div className="sample-preview-header">
              <strong>Planted Backdoors &amp; Duplicates</strong>
              <span className="sample-tag" style={{ color: '#ef4444', background: '#ef444422', border: '1px solid #ef444444' }}>
                Synthetic Corpus
              </span>
            </div>
            <p className="sample-vector">
              Detects token-level backdoor triggers, exact duplicates, and MinHash/LSH near-duplicates.
            </p>
            <div className="sample-layer">Screening: <code>Pre-Retrieval Isolation</code></div>
          </div>
          <button
            className="btn btn--primary"
            style={{ width: '100%' }}
            onClick={handleTestDemo}
            disabled={scanning}
          >
            Test 1,000-Row Planted Demo
          </button>
        </div>

        <div className="upload-card">
          <h3 className="section-title">Upload Custom Dataset</h3>
          <p className="field-hint" style={{ marginBottom: 12 }}>
            Upload CSV or JSONL corpus containing a &apos;text&apos; column.
          </p>
          <DropZone onFile={handleScan} disabled={scanning} accept=".csv,.jsonl" maxSizeMB={200} />
        </div>
      </div>

      {scanning && <ScanProgress filename={filename} stage="Analyzing dataset rows..." />}
      {error && <div className="error-banner fade-in">{error}</div>}

      {result && result.summary.status === 'completed' && (
        <div className="results-area slide-up">
          <div className="metrics-grid">
            <MetricCard value={result.summary.total} label="Total Rows" sub="Parsed & analyzed" />
            <MetricCard value={result.summary.quarantined} label="Poisoned Rows" sub="Backdoor triggers isolated" color="#ef4444" borderColor="#ef4444" />
            <MetricCard value={result.summary.duplicates} label="Exact Duplicates" sub="Deduplicated" color="#f59e0b" borderColor="#f59e0b" />
            <MetricCard value={result.summary.near_duplicates} label="Near Duplicates" sub="High lexical similarity" color="#8b5cf6" borderColor="#8b5cf6" />
          </div>

          {result.summary.trigger_tokens.length > 0 && (
            <div className="dataset-section fade-in">
              <h3 className="section-title">Suspicious Backdoor Trigger Tokens</h3>
              <div className="token-list">
                {result.summary.trigger_tokens.map(t => (
                  <code key={t} className="trigger-token">{t}</code>
                ))}
              </div>
            </div>
          )}

          <div className="download-grid">
            <button className="btn btn--primary" onClick={() => downloadFile(result.report, 'report.json')}>Download report.json</button>
            <button className="btn btn--outline" onClick={() => downloadFile(result.screened, 'screened.jsonl')}>Download screened.jsonl</button>
            <button className="btn btn--outline" onClick={() => downloadFile(result.quarantined, 'quarantined.jsonl')}>Download quarantined.jsonl</button>
          </div>
        </div>
      )}

      {result && result.summary.status !== 'completed' && (
        <div className="error-banner fade-in">Dataset could not be screened: {result.summary.reason}</div>
      )}

      {!result && !scanning && (
        <div className="empty-state fade-in">Upload a CSV or JSONL dataset to begin poison screening.</div>
      )}
    </div>
  )
}
