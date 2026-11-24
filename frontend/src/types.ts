export interface AppConfig {
  tier: 'external_upload' | 'internal_kb'
  llm: 'mock' | 'real'
  analyst: string
}

export type ScanStatus = 'clean' | 'flagged' | 'review_required' | 'unsupported' | 'scan_failed'

export interface IngestResult {
  status: ScanStatus
  doc_id: string
  indexed: boolean
  reason?: string
  quarantined_ids?: string[]
  review_ids?: string[]
  index_version?: number
  policy_version?: string
  filename?: string
}

export interface Finding {
  sentence_id: string
  score: number
  status: string
  decision_reason: string
  signals: { type: string; weight: number }[]
}

export interface ReviewItem {
  sentence_id: string
  doc_id: string
  text: string
  status: string
  decision_reason: string
}

export interface TraceResult {
  output: string
  doc_sha256: string
  retrieved_chunk_ids: string[]
}

export interface HealthResponse {
  status: string
  version: string
  policy_version: string
  tier: string
  guard: string
  real_llm_configured: boolean
}

export interface DatasetSummary {
  status: string
  total: number
  quarantined: number
  duplicates: number
  near_duplicates: number
  trigger_tokens: string[]
  reason?: string
}

export interface DatasetResult {
  summary: DatasetSummary
  report: {
    trigger_token_stats: { token: string; masked_disagreement: number }[]
    samples: Record<string, unknown>[]
  } | null
  screened: Record<string, unknown>[]
  quarantined: Record<string, unknown>[]
}

export interface DocumentMeta {
  forensic_path?: string
  sha256?: string
  media_type?: string
  pages?: number
  final_status?: string
}

export interface Sentence {
  sentence_id: string
  text: string
}

export interface SampleInfo {
  label: string
  file: string
  title: string
  tag: string
  badge_color: string
  vector: string
  layer: string
}
