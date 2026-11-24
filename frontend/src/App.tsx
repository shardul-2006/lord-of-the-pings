import { useState } from 'react'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import { DocumentConsole } from './pages/DocumentConsole'
import { DatasetGate } from './pages/DatasetGate'
import { Architecture } from './pages/Architecture'
import type { AppConfig } from './types'

type Page = 'documents' | 'dataset' | 'architecture'

export default function App() {
  const [page, setPage] = useState<Page>('documents')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [config, setConfig] = useState<AppConfig>({
    tier: 'external_upload',
    llm: 'mock',
    analyst: 'secops_analyst_01',
  })

  return (
    <div className="app-root">
      <Sidebar
        open={sidebarOpen}
        config={config}
        onConfigChange={setConfig}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />
      <div className={`main-area ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
        <Header config={config} />
        <nav className="page-nav">
          {(['documents', 'dataset', 'architecture'] as Page[]).map((p) => (
            <button
              key={p}
              className={`nav-tab ${page === p ? 'active' : ''}`}
              onClick={() => setPage(p)}
            >
              {p === 'documents' && 'Document Security Console'}
              {p === 'dataset' && 'Dataset Gate'}
              {p === 'architecture' && 'Threat Model'}
            </button>
          ))}
        </nav>
        <main className="page-content">
          <div className={`page-panel ${page === 'documents' ? 'visible' : ''}`}>
            <DocumentConsole config={config} />
          </div>
          <div className={`page-panel ${page === 'dataset' ? 'visible' : ''}`}>
            <DatasetGate config={config} />
          </div>
          <div className={`page-panel ${page === 'architecture' ? 'visible' : ''}`}>
            <Architecture />
          </div>
        </main>
      </div>
    </div>
  )
}
