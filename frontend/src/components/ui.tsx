import type { ReactNode } from 'react'
import { statusTone } from '../lib/format'
import type { AnalysisMode, Status } from '../lib/types'

export function Badge({ tone, children, title }: { tone: string; children: ReactNode; title?: string }) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status: Status }) {
  return <Badge tone={statusTone(status)}>{status}</Badge>
}

const MODE_TONE: Record<AnalysisMode, string> = {
  llm: 'info',
  'recorded fixture': 'muted',
  'rules-only fallback': 'warn',
}

export function ModeBadges({ modes }: { modes: AnalysisMode[] }) {
  if (modes.length === 0) return <Badge tone="warn">not analysed</Badge>
  return (
    <>
      {modes.map((m) => (
        <Badge key={m} tone={MODE_TONE[m]}>
          {m}
        </Badge>
      ))}
    </>
  )
}

export function Errors({ reasons }: { reasons: string[] | null }) {
  if (!reasons || reasons.length === 0) return null
  return (
    <div className="errors" role="alert">
      <ul>
        {reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </div>
  )
}

export function Loading() {
  return <p className="muted">Loading…</p>
}

/** Wide tables scroll inside this box, so the page never scrolls sideways at 390 px. */
export function TableWrap({ children }: { children: ReactNode }) {
  return <div className="table-wrap">{children}</div>
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {children}
    </section>
  )
}
