import { useState } from 'react'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import Scanner from './components/Scanner/Scanner'
import { DocumentConsole } from './pages/DocumentConsole'
import { DatasetGate } from './pages/DatasetGate'
import { Architecture } from './pages/Architecture'
import { DocumentScanIcon, DatabaseIcon, LayersIcon } from './components/icons'
import type { AppConfig } from './types'

type Page = 'documents' | 'dataset' | 'architecture'

const NAV_ITEMS: { id: Page; label: string; tag: string; Icon: typeof DocumentScanIcon }[] = [
  { id: 'documents', label: 'Document Security Console', tag: '4-LAYER SCREENING', Icon: DocumentScanIcon },
  { id: 'dataset', label: 'Dataset Gate', tag: 'CORPUS QUARANTINE', Icon: DatabaseIcon },
  { id: 'architecture', label: 'Threat Model', tag: 'DEFENSE TOPOLOGY', Icon: LayersIcon },
]

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
      <div className="scanner-background-canvas" aria-hidden="true">
        <Scanner
          color1="#10063f"
          color2="#0653a9"
          color3="#FFFFFF"
          speed={0.4}
          sweepSpeed={0.22}
          sweepWidth={1.6}
          trail={0.5}
          ripple={0.22}
          bandDensity={11}
          glow={0.6}
          scanDirection="vertical"
          colorSpread={0.7}
          scanline
          scanlineIntensity={0.4}
          mouseInteraction
          clickEffect="ping"
          reverse={false}
          scale={1.5}
          frequency={2}
          lineWidth={1.2}
          brightness={0.9}
          vignette={0.35}
          grain
          grainIntensity={0.04}
          opacity={0.65}
          mouseMode="repel"
          mouseRadius={0.5}
          mouseStrength={0.7}
          intro
          lightMode={false}
        />
      </div>
      <Sidebar
        open={sidebarOpen}
        config={config}
        onConfigChange={setConfig}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />
      <div className={`main-area ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
        <Header config={config} />
        <nav className="page-nav" aria-label="Primary sections">
          <div className="page-nav-track">
            {NAV_ITEMS.map(({ id, label, tag, Icon }) => {
              const active = page === id
              return (
                <button
                  key={id}
                  className={`nav-tab ${active ? 'active' : ''}`}
                  onClick={() => setPage(id)}
                  aria-current={active ? 'page' : undefined}
                >
                  <span className="nav-tab-icon">
                    <Icon size={16} />
                  </span>
                  <span className="nav-tab-text">
                    <span className="nav-tab-label">{label}</span>
                    <span className="nav-tab-tag">{tag}</span>
                  </span>
                  {active && <span className="nav-tab-indicator" />}
                </button>
              )
            })}
          </div>
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
