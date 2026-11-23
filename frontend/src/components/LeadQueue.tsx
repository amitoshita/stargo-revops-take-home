import { formatIL, scoreLabel } from '../lib/format'
import { href } from '../lib/route'
import type { LeadRow } from '../lib/types'
import { Badge, ModeBadges, ReviewFlags, StatusBadge, TableWrap } from './ui'

export function LeadQueue({ rows }: { rows: LeadRow[] }) {
  if (rows.length === 0) return <p className="muted">No leads yet.</p>
  return (
    <TableWrap>
      <table className="queue">
        <thead>
          <tr>
            <th>Name</th>
            <th>Company</th>
            <th>Channel</th>
            <th>Received (Israel)</th>
            <th>Score</th>
            <th>Status</th>
            <th>Owner</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.person_id}>
              <td>
                <a href={href({ view: 'lead', personId: row.person_id })} dir="auto">
                  {row.name ?? row.person_id}
                </a>
                {row.message_count > 1 && <span className="muted"> ({row.message_count} msgs)</span>}
                <div className="badges">
                  <ModeBadges modes={row.analysis_modes} />
                  {row.expansion && <Badge tone="info">expansion</Badge>}
                  {row.status !== 'needs review' && <ReviewFlags flags={row.review_flags} />}
                </div>
              </td>
              <td>
                {row.company ?? <span className="muted">unknown</span>}
                {row.company_source === 'stated' && <span className="muted"> (stated)</span>}
              </td>
              <td>{row.channel.replace('_', ' ')}</td>
              <td className="nowrap">{formatIL(row.received_at)}</td>
              <td>
                <Badge tone={row.band === 'A' ? 'good' : row.band === 'B' ? 'info' : 'muted'}>
                  {scoreLabel(row.score, row.band)}
                </Badge>
              </td>
              <td>
                <StatusBadge status={row.status} />
                {row.accepted_by && row.status !== 'QL' && (
                  <div className="muted small">accepted by {row.accepted_by}</div>
                )}
              </td>
              <td>{row.owner ?? <span className="muted">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  )
}
