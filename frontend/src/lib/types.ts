// Mirrors of the backend response models (backend/app/api/schemas.py and friends).

export type Status =
  | 'QL candidate'
  | 'QL'
  | 'excluded'
  | 'disqualified'
  | 'nurture'
  | 'suppressed'
  | 'needs review'

export type AnalysisMode = 'llm' | 'recorded fixture' | 'rules-only fallback'
export type Tri = 'pass' | 'fail' | 'unknown'

export interface Mode {
  llm_enabled: boolean
  label: string
  model: string | null
  seed_analysis: string
  pasted_analysis: string
}

export interface LeadRow {
  person_id: string
  name: string | null
  company: string | null
  company_source: 'crm' | 'crm_company_record' | 'stated' | 'none'
  channel: string
  received_at: string
  message_count: number
  status: Status
  owner: string | null
  score: number | null
  band: 'A' | 'B' | 'nurture' | null
  analysis_modes: AnalysisMode[]
  expansion: boolean
  accepted_by: string | null
}

export interface Evidence {
  field: string
  quote: string
  translation: string | null
}

export interface Extraction {
  language: string
  intent: string
  interest_level: string
  buyer_role: string | null
  data_problem: string | null
  problem_category: string
  volume_stated: boolean
  company_facts: {
    company_name: string | null
    employees: number | null
    country: string | null
    vertical: string | null
    is_software_vendor: boolean
  }
  timing: string
  instruction_attempt: boolean
  evidence: Evidence[]
}

export interface MessageAnalysis {
  inbound_id: string
  mode: AnalysisMode
  extraction: Extraction | null
  failure: { kind: string; detail: string } | null
  injection_signals: string[]
}

export interface Condition {
  status: Tri
  reason: string
  evidence: string[]
  source: string
  verified: boolean
}

export interface Checklist {
  c1_company_fit: Condition
  c2_relevant_buyer: Condition
  c3_data_problem: Condition
  c4_expressed_interest: Condition
  c5_sales_acceptance: Condition
}

export interface ScoreFactor {
  name: string
  points: number
  max: number
  basis: string
  unknown: boolean
}

export interface Assessment {
  status: Status
  reason: string
  checklist: Checklist | null
  owner: string | null
  owner_basis: string
  score: number | null
  band: 'A' | 'B' | 'nurture' | null
  breakdown: ScoreFactor[]
  rationale: string
  accepted_by: { decision_id: string; decided_by: string; decided_at: string } | null
  expansion: boolean
}

export interface Decision {
  id: string
  origin: string
  contact_email: string
  decision: 'accepted' | 'rejected'
  decided_by: string
  decided_at: string
  note: string | null
}

export interface Draft {
  person_id: string
  reply_draft: string | null
  draft_mode: AnalysisMode | null
  draft_requires_human_approval: true
}

export interface Message {
  id: string
  origin: string
  channel: string
  source: string | null
  received_at: string
  subject: string | null
  body: string
  analysis: MessageAnalysis | null
}

export interface LeadDetail {
  person_id: string
  name: string | null
  company: string | null
  company_source: string
  crm: Record<string, unknown> | null
  messages: Message[]
  assessment: Assessment
  decisions: Decision[]
  draft: Draft | null
  draft_available: boolean
}

export interface RecordRef {
  record_id: string
  person_id: string
  name: string | null
  detail: string
}

export interface KpiMetric {
  key: string
  label: string
  actual: number
  target: number
  gap: number
  records: RecordRef[]
}

export interface SourceRow {
  source: string
  count: number | null
  feed_status: string | null
  records: RecordRef[]
  note: string | null
}

export interface KpiPack {
  week_start: string
  week_end: string
  timezone: string
  generated_at: string
  analysis_modes: AnalysisMode[]
  metrics: KpiMetric[]
  by_source: SourceRow[]
  expansion: {
    accepted: RecordRef[]
    meetings_booked: RecordRef[]
    meetings_held: RecordRef[]
    opportunities: RecordRef[]
  }
  excluded: { record_id: string; name: string | null; reason: string }[]
  caveats: string[]
}

export type AnswerState = 'owned' | 'mentioned_unowned' | 'absent' | 'wrong'

export interface GapScore {
  prompt_id: string
  prompt: string
  cluster: string
  priority: number
  per_engine: Record<string, AnswerState>
  state_sum: number
  fit: number
  fit_basis: string
  competitors: string[]
  score: number
  rank: number
  explanation: string
}

export interface GeoReport {
  gaps: GapScore[]
  risks: { answer_id: string; prompt_id: string; engine: string; kind: string; detail: string }[]
  formula: string
}

export interface Claimed {
  text: string
  refs: string[]
}

export interface ContentBrief {
  prompt_id: string
  draft: {
    title: string
    direct_answer: Claimed
    sections: { heading: string; paragraphs: Claimed[] }[]
    faq: { question: string; answer: Claimed[] }[]
    schema_org_type: string
  }
  mode: string
  model: string | null
  flags: { location: string; rule: string; severity: 'block' | 'warn'; text: string }[]
  publishable: boolean
}

export interface PasteForm {
  from_name: string
  from_email: string
  linkedin_url: string
  channel: string
  source: string
  subject: string
  body: string
  received_at: string
}
