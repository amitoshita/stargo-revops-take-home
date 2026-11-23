import { useState } from 'react'
import { api, ApiError } from '../lib/api'
import { stateLabel } from '../lib/format'
import type { Claimed, ContentBrief, GeoReport } from '../lib/types'
import { Badge, Errors, Section, TableWrap } from './ui'

const ENGINES = ['ChatGPT', 'Perplexity', 'Gemini']

function ClaimText({ claim }: { claim: Claimed }) {
  return (
    <>
      {claim.text}{' '}
      {claim.refs.map((r) => (
        <code key={r} className="ref">
          {r}
        </code>
      ))}
    </>
  )
}

export function GeoView({ report, brief, onBrief }: { report: GeoReport; brief: ContentBrief | null; onBrief: () => void }) {
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[] | null>(null)

  async function regenerate() {
    setBusy(true)
    setErrors(null)
    try {
      await api.post('/geo/brief')
      onBrief()
    } catch (err) {
      setErrors(err instanceof ApiError ? err.reasons : ['could not generate a brief'])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <Section title="AI visibility gaps">
        <p className="muted small">{report.formula}</p>
        <TableWrap>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Prompt</th>
                <th>Score</th>
                {ENGINES.map((e) => (
                  <th key={e}>{e}</th>
                ))}
                <th>Competitors</th>
              </tr>
            </thead>
            <tbody>
              {report.gaps.map((g) => (
                <tr key={g.prompt_id} title={g.explanation}>
                  <td>{g.rank}</td>
                  <td>
                    <strong>{g.prompt_id}</strong> {g.prompt}
                    <div className="muted small">{g.fit ? g.fit_basis : 'no BC-3 product: not a content gap'}</div>
                  </td>
                  <td>{g.score}</td>
                  {ENGINES.map((e) => (
                    <td key={e} className={`state-${g.per_engine[e]}`}>
                      {g.per_engine[e] ? stateLabel(g.per_engine[e]) : '—'}
                    </td>
                  ))}
                  <td className="small">{g.competitors.join(', ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>

      <Section title="Brand-accuracy risks">
        <ul>
          {report.risks.map((r) => (
            <li key={`${r.answer_id}-${r.kind}-${r.detail}`}>
              <Badge tone={r.kind === 'wrong_claim' ? 'bad' : 'warn'}>{r.kind.replace('_', ' ')}</Badge>{' '}
              <code>{r.answer_id}</code> {r.detail}
            </li>
          ))}
        </ul>
      </Section>

      <Section title={`Content brief for the top gap${brief ? ` (${brief.prompt_id})` : ''}`}>
        {brief ? (
          <article className="brief">
            <div className="badges">
              <Badge tone={brief.publishable ? 'good' : 'bad'}>
                {brief.publishable ? 'publishable' : 'blocked by claim validator'}
              </Badge>
              <Badge tone="muted">
                {brief.mode}
                {brief.model ? ` · ${brief.model}` : ''}
              </Badge>
              <Badge tone="muted">schema.org: {brief.draft.schema_org_type}</Badge>
            </div>
            {brief.flags.length > 0 && (
              <ul className="flags">
                {brief.flags.map((f, i) => (
                  <li key={i} className={`flag-${f.severity}`}>
                    <strong>{f.severity}</strong> {f.location}: {f.rule}
                    {f.text && (
                      <div className="small muted" dir="auto">
                        “{f.text}”
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <h3>{brief.draft.title}</h3>
            <p className="lead-answer">
              <ClaimText claim={brief.draft.direct_answer} />
            </p>
            {brief.draft.sections.map((s) => (
              <div key={s.heading}>
                <h4>{s.heading}</h4>
                {s.paragraphs.map((p, i) => (
                  <p key={i}>
                    <ClaimText claim={p} />
                  </p>
                ))}
              </div>
            ))}
            <h4>FAQ</h4>
            <dl>
              {brief.draft.faq.map((f) => (
                <div key={f.question}>
                  <dt>{f.question}</dt>
                  {f.answer.map((a, i) => (
                    <dd key={i}>
                      <ClaimText claim={a} />
                    </dd>
                  ))}
                </div>
              ))}
            </dl>
          </article>
        ) : (
          <p className="muted">No brief yet.</p>
        )}
        <button type="button" onClick={regenerate} disabled={busy}>
          {busy ? 'Generating…' : 'Regenerate brief'}
        </button>
        <Errors reasons={errors} />
      </Section>
    </div>
  )
}
