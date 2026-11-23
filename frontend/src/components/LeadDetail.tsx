import { useState } from 'react'
import { api, ApiError } from '../lib/api'
import { formatIL, ilLocalToIso, nowILLocal, scoreLabel, triIcon } from '../lib/format'
import type { Assessment, Checklist, Draft, Extraction, LeadDetail as Detail, Message } from '../lib/types'
import { Badge, Errors, ModeBadges, Section, StatusBadge, TableWrap } from './ui'

const CONDITIONS: [keyof Checklist, string][] = [
  ['c1_company_fit', 'C1 Company fit'],
  ['c2_relevant_buyer', 'C2 Relevant buyer'],
  ['c3_data_problem', 'C3 Data problem'],
  ['c4_expressed_interest', 'C4 Expressed interest'],
  ['c5_sales_acceptance', 'C5 Sales acceptance'],
]

export function LeadDetailView({ detail, onChange }: { detail: Detail; onChange: () => void }) {
  const a = detail.assessment
  return (
    <div className="stack">
      <section className="card">
        <h1>{detail.name ?? detail.person_id}</h1>
        <p className="muted">
          {detail.company ?? 'Company unknown'}
          {detail.company_source === 'stated' && ' (stated, unverified)'} · {detail.person_id}
        </p>
        <div className="badges">
          <StatusBadge status={a.status} />
          <Badge tone="muted">owner: {a.owner ?? '—'}</Badge>
          <Badge tone={a.band === 'A' ? 'good' : 'muted'}>score {scoreLabel(a.score, a.band)}</Badge>
          {a.accepted_by && <Badge tone="info">accepted by {a.accepted_by.decided_by}</Badge>}
        </div>
        <p className="rationale">{a.rationale}</p>
        <p className="muted small">Owner basis: {a.owner_basis}</p>
      </section>

      <Section title="Messages">
        {detail.messages.map((m) => (
          <MessageCard key={m.id} message={m} />
        ))}
      </Section>

      {a.checklist ? (
        <Section title="QL checklist">
          <ChecklistTable checklist={a.checklist} />
        </Section>
      ) : (
        <Section title="QL checklist">
          <p className="muted">Not evaluated: {a.reason.replace(/_/g, ' ')}.</p>
        </Section>
      )}

      {a.breakdown.length > 0 && (
        <Section title="Score breakdown">
          <Breakdown assessment={a} />
        </Section>
      )}

      <Section title="Reply draft">
        <DraftPanel detail={detail} onChange={onChange} />
      </Section>

      <Section title="Sales decision">
        <DecisionForm personId={detail.person_id} onDone={onChange} />
        {detail.decisions.length > 0 && (
          <TableWrap>
            <table>
              <thead>
                <tr>
                  <th>Id</th>
                  <th>Decision</th>
                  <th>By</th>
                  <th>Decided (Israel)</th>
                </tr>
              </thead>
              <tbody>
                {detail.decisions.map((d, i) => (
                  <tr key={d.id} className={i < detail.decisions.length - 1 ? 'superseded' : ''}>
                    <td>{d.id}</td>
                    <td>{d.decision}</td>
                    <td>{d.decided_by}</td>
                    <td className="nowrap">{formatIL(d.decided_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">The latest decision wins; earlier ones are kept for history.</p>
          </TableWrap>
        )}
      </Section>
    </div>
  )
}

function MessageCard({ message }: { message: Message }) {
  const analysis = message.analysis
  return (
    <article className="message">
      <header className="muted small">
        {message.id} · {message.channel.replace('_', ' ')} · {formatIL(message.received_at)} ·
        source {message.source ?? 'not recorded'}
      </header>
      {message.subject && <p className="subject">{message.subject}</p>}
      {/* Rendered as text, never as HTML: message content is untrusted. */}
      <blockquote>{message.body}</blockquote>
      {analysis && (
        <div className="analysis">
          <div className="badges">
            <ModeBadges modes={[analysis.mode]} />
            {analysis.injection_signals.length > 0 && (
              <Badge tone="warn" title={analysis.injection_signals.join(', ')}>
                instruction attempt: not analysed
              </Badge>
            )}
            {analysis.failure && (
              <Badge tone="warn" title={analysis.failure.detail}>
                analysis failed: {analysis.failure.kind.replace('_', ' ')}
              </Badge>
            )}
          </div>
          {analysis.extraction && <ExtractionView extraction={analysis.extraction} />}
        </div>
      )}
    </article>
  )
}

function ExtractionView({ extraction: e }: { extraction: Extraction }) {
  const facts = Object.entries(e.company_facts).filter(([, v]) => v !== null && v !== false)
  return (
    <dl className="facts">
      <dt>Language</dt>
      <dd>{e.language}</dd>
      <dt>Intent</dt>
      <dd>
        {e.intent} ({e.interest_level.replace('_', ' ')})
      </dd>
      <dt>Role</dt>
      <dd>{e.buyer_role ?? '—'}</dd>
      <dt>Problem</dt>
      <dd>
        {e.data_problem ?? '—'} <span className="muted">[{e.problem_category}]</span>
      </dd>
      <dt>Stated facts</dt>
      <dd>{facts.length ? facts.map(([k, v]) => `${k}: ${String(v)}`).join(' · ') : '—'}</dd>
      <dt>Timing</dt>
      <dd>{e.timing.replace('_', ' ')}</dd>
      <dt>Evidence</dt>
      <dd>
        <ul className="evidence">
          {e.evidence.map((ev, i) => (
            <li key={i}>
              <span className="muted">{ev.field}:</span> “{ev.quote}”
              {ev.translation && <span className="muted"> ({ev.translation})</span>}
            </li>
          ))}
        </ul>
      </dd>
    </dl>
  )
}

function ChecklistTable({ checklist }: { checklist: Checklist }) {
  return (
    <ul className="checklist">
      {CONDITIONS.map(([key, label]) => {
        const c = checklist[key]
        return (
          <li key={key} className={`tri-${c.status}`}>
            <span className="tri">{triIcon(c.status)}</span>
            <div>
              <strong>{label}</strong> — {c.reason}
              {c.source === 'message' && <span className="muted"> (stated, unverified)</span>}
              {c.evidence.length > 0 && (
                <ul className="evidence">
                  {c.evidence.map((ev, i) => (
                    <li key={i}>{ev}</li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function Breakdown({ assessment }: { assessment: Assessment }) {
  return (
    <TableWrap>
      <table>
        <thead>
          <tr>
            <th>Factor</th>
            <th>Points</th>
            <th>Basis</th>
          </tr>
        </thead>
        <tbody>
          {assessment.breakdown.map((f) => (
            <tr key={f.name}>
              <td>{f.name}</td>
              <td className="nowrap">
                {f.points} / {f.max}
              </td>
              <td>{f.unknown ? <span className="muted">unknown — {f.basis}</span> : f.basis}</td>
            </tr>
          ))}
          <tr>
            <td>
              <strong>Total</strong>
            </td>
            <td>
              <strong>{assessment.score}</strong>
            </td>
            <td className="muted">Band {assessment.band}. The score never overrides the QL gate.</td>
          </tr>
        </tbody>
      </table>
    </TableWrap>
  )
}

function DraftPanel({ detail, onChange }: { detail: Detail; onChange: () => void }) {
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[] | null>(null)
  const draft: Draft | null = detail.draft
  if (!detail.draft_available) {
    return <p className="muted">No draft for this status. Nothing is ever sent.</p>
  }
  async function generate() {
    setBusy(true)
    setErrors(null)
    try {
      await api.post(`/leads/${encodeURIComponent(detail.person_id)}/draft`)
      onChange()
    } catch (err) {
      setErrors(err instanceof ApiError ? err.reasons : ['could not create a draft'])
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      {draft?.reply_draft ? (
        <>
          <div className="badges">
            <Badge tone="warn">needs human approval · not sent</Badge>
            {draft.draft_mode && <ModeBadges modes={[draft.draft_mode]} />}
          </div>
          <pre className="draft">{draft.reply_draft}</pre>
        </>
      ) : (
        <p className="muted">No draft yet.</p>
      )}
      <button type="button" onClick={generate} disabled={busy}>
        {draft ? 'Regenerate draft' : 'Draft a reply'}
      </button>
      <Errors reasons={errors} />
    </div>
  )
}

export function DecisionForm({ personId, onDone }: { personId: string; onDone: () => void }) {
  const [decidedBy, setDecidedBy] = useState('')
  const [decidedAt, setDecidedAt] = useState(() => nowILLocal())
  const [note, setNote] = useState('')
  const [errors, setErrors] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(decision: 'accepted' | 'rejected') {
    setErrors(null)
    if (!decidedBy.trim()) {
      setErrors(['Enter who decided.'])
      return
    }
    setBusy(true)
    try {
      await api.post(`/leads/${encodeURIComponent(personId)}/decisions`, {
        decision,
        decided_by: decidedBy.trim(),
        decided_at: ilLocalToIso(decidedAt),
        note: note.trim() || null,
      })
      setNote('')
      onDone()
    } catch (err) {
      setErrors(err instanceof ApiError ? err.reasons : ['could not save the decision'])
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form" onSubmit={(e) => e.preventDefault()}>
      <label>
        Decided by
        <input value={decidedBy} onChange={(e) => setDecidedBy(e.target.value)} placeholder="e.g. Leo" />
      </label>
      <label>
        Decided at (Israel time)
        <input type="datetime-local" value={decidedAt} onChange={(e) => setDecidedAt(e.target.value)} />
      </label>
      <label>
        Note (optional)
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="row">
        <button type="button" className="good" disabled={busy} onClick={() => submit('accepted')}>
          Accept
        </button>
        <button type="button" className="bad" disabled={busy} onClick={() => submit('rejected')}>
          Reject
        </button>
      </div>
      <p className="muted small">
        A decision counts in the week of its decided-at time, so a past week can be replayed.
      </p>
      <Errors reasons={errors} />
    </form>
  )
}
