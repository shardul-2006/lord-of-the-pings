const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...init?.headers },
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${body || res.statusText}`)
  }
  return res.json()
}

export async function health() {
  return request<import('./types').HealthResponse>('/health')
}

export async function ingest(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<import('./types').IngestResult>('/ingest', {
    method: 'POST',
    body: form,
  })
}

export async function getFindings(docId: string) {
  return request<{
    document: import('./types').DocumentMeta
    findings: import('./types').Finding[]
    withheld: import('./types').ReviewItem[]
    events: { action: string; sentence_id: string; actor: string; at: string }[]
  }>(`/findings/${docId}`)
}

export async function ask(docId: string, question: string, llm: string, spotlight: boolean) {
  return request<{
    status: string
    vulnerable: import('./types').TraceResult
    defended: import('./types').TraceResult
    output_check: { canary_leak: boolean; stripped: string[]; ungrounded: string[] }
  }>('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId, question, llm, spotlight }),
  })
}

export async function release(sentenceId: string, reviewer: string) {
  return request<{ released: boolean; index_version?: number; reason?: string }>(
    `/release/${sentenceId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer }),
    }
  )
}

export async function requarantine(sentenceId: string, reviewer: string) {
  return request<{ index_version: number }>(
    `/requarantine/${sentenceId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer }),
    }
  )
}

export function overlayUrl(docId: string, page: number) {
  return `${BASE}/overlay/${docId}/${page}`
}

export async function runIntegrity(docId: string, task: string, llm: string) {
  return request<Record<string, unknown>>('/integrity', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId, task, llm }),
  })
}

export async function screenDataset(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<import('./types').DatasetResult>('/dataset', {
    method: 'POST',
    body: form,
  })
}

export async function getSamples() {
  return request<import('./types').SampleInfo[]>('/samples')
}

export async function ingestSample(sampleName: string) {
  return request<import('./types').IngestResult>(`/samples/${sampleName}/ingest`, {
    method: 'POST',
  })
}

export async function screenDemoDataset() {
  return request<import('./types').DatasetResult>('/demo-dataset/screen', {
    method: 'POST',
  })
}
