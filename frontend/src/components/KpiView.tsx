import { Fragment, useState } from 'react'
import { shiftWeek } from '../lib/format'
import type { KpiPack, RecordRef } from '../lib/types'
import { Section, TableWrap } from './ui'

function Refs({ refs }: { refs: RecordRef[] }) {
  if (refs.length === 0) return <span className="muted">—</span>
  return (
    <ul className="refs">
      {refs.map((r) => (
        <li key={r.record_id}>
          <code>{r.record_id}</code> {r.name ?? r.person_id} <span className="muted small">{r.detail}</span>
        </li>
      ))}
    </ul>
  )
}

export function KpiView({ pack, week, onWeek }: { pack: KpiPack; week: string; onWeek: (w: string) => void }) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="stack">
      <section className="card">
        <h1>Weekly KPI pack</h1>
        <div className="row">
          <button type="button" onClick={() => onWeek(shiftWeek(week, -1))}>
            ← Previous
          </button>
          <span>
            Sun {pack.week_start} – Thu {pack.week_end} ({pack.timezone})
          </span>
          <button type="button" onClick={() => onWeek(shiftWeek(week, 1))}>
            Next →
          </button>
        </div>
        <p className="muted small">
          Analysis mode: {pack.analysis_modes.join(', ') || 'n/a'} · <a href={`/api/kpi/markdown?week=${week}`}>markdown</a>
        </p>
      </section>

      <Section title="Acquisition vs target">
        <TableWrap>
          <table>
            <thead>
              <tr>
                <th>KPI</th>
                <th>Actual</th>
                <th>Target</th>
                <th>Gap</th>
              </tr>
            </thead>
            <tbody>
              {pack.metrics.map((m) => (
                <Fragment key={m.key}>
                  <tr>
                    <td>
                      <button type="button" className="link" onClick={() => setOpen(open === m.key ? null : m.key)}>
                        {open === m.key ? '▾' : '▸'} {m.label}
                      </button>
                    </td>
                    <td>{m.actual}</td>
                    <td>{m.target}</td>
                    <td className={m.gap < 0 ? 'neg' : ''}>{m.gap}</td>
                  </tr>
                  {open === m.key && (
                    <tr>
                      <td colSpan={4}>
                        <Refs refs={m.records} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>

      <Section title="QLs by first-touch source">
        <TableWrap>
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>QLs</th>
                <th>Records</th>
              </tr>
            </thead>
            <tbody>
              {pack.by_source.map((s) => (
                <tr key={s.source}>
                  <td>{s.source}</td>
                  <td>{s.count === null ? <strong>unknown</strong> : s.count}</td>
                  <td>
                    <Refs refs={s.records} />
                    {s.note && <div className="muted small">{s.note}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>

      <Section title="Expansion (existing customers)">
        <TableWrap>
          <table>
            <tbody>
              {(
                [
                  ['Accepted', pack.expansion.accepted],
                  ['Meetings booked', pack.expansion.meetings_booked],
                  ['Meetings held', pack.expansion.meetings_held],
                  ['Opportunities', pack.expansion.opportunities],
                ] as const
              ).map(([label, refs]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td>{refs.length}</td>
                  <td>
                    <Refs refs={[...refs]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>

      <Section title="Not counted this week">
        <TableWrap>
          <table>
            <tbody>
              {pack.excluded.map((x) => (
                <tr key={x.record_id}>
                  <td>
                    <code>{x.record_id}</code>
                  </td>
                  <td>{x.name ?? '—'}</td>
                  <td className="small">{x.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>

      {pack.caveats.length > 0 && (
        <Section title="Caveats">
          <ul>
            {pack.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}
