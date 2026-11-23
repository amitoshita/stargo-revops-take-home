import type { Mode } from '../lib/types'

export function ModeBanner({ mode }: { mode: Mode | null }) {
  if (!mode) return null
  if (!mode.llm_enabled) {
    return (
      <div className="banner banner-warn" role="status">
        <strong>Rules-only fallback mode.</strong> No LLM key is configured. Seed messages use
        recorded LLM answers; pasted messages are read by keyword rules (English only; anything
        else goes to needs review). Drafts use templates.
      </div>
    )
  }
  return (
    <div className="banner banner-info" role="status">
      <strong>LLM mode</strong> ({mode.model}). Seed messages use recorded answers; pasted messages
      are analysed live. Nothing is ever sent: drafts need human approval.
    </div>
  )
}
