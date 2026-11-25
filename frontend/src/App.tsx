import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import Scanner from './components/Scanner/Scanner'
import { DocumentConsole } from './pages/DocumentConsole'
import { DatasetGate } from './pages/DatasetGate'
import { Architecture } from './pages/Architecture'
import { FileIcon, DatabaseIcon, LayersIcon } from './components/icons'
import type { AppConfig } from './types'

type Page = 'documents' | 'dataset' | 'architecture'

export default function App() {
  const [page, setPage] = useState<Page>('documents')
  const [sidebarOpen, setSidebarOpen] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth > 1024 : true
  )
  const [config, setConfig] = useState<AppConfig>({
    tier: 'external_upload',
    llm: 'mock',
    analyst: 'secops_analyst_01',
  })

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth <= 1024) {
        setSidebarOpen(false)
      }
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <div className="app-root">
      <div className="scanner-background-canvas" aria-hidden="true">
        <Scanner
          color1="#090d12"
          color2="#0d6e66"
          color3="#5eead4"
          speed={0.42}
          sweepSpeed={0.24}
          sweepWidth={1.6}
          trail={0.55}
          ripple={0.24}
          bandDensity={11}
          glow={0.65}
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
          brightness={0.95}
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
        <Header config={config} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <nav className="page-nav" aria-label="Primary navigation">
          <div className="page-nav-inner">
            {([
              { id: 'documents', label: 'Document Security Console', Icon: FileIcon },
              { id: 'dataset', label: 'Dataset Gate', Icon: DatabaseIcon },
              { id: 'architecture', label: 'Threat Model', Icon: LayersIcon },
            ] as { id: Page; label: string; Icon: typeof FileIcon }[]).map(({ id, label, Icon }) => (
              <button
                key={id}
                type="button"
                className={`nav-tab ${page === id ? 'active' : ''}`}
                onClick={() => setPage(id)}
              >
                <Icon size={15} />
                <span>{label}</span>
              </button>
            ))}
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
