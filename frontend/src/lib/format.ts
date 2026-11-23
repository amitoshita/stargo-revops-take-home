// Formatting helpers. All times are shown in Asia/Jerusalem, whatever the browser's zone.

import type { AnswerState, Status, Tri } from './types'

export const IL_TZ = 'Asia/Jerusalem'

const dateTime = new Intl.DateTimeFormat('en-GB', {
  timeZone: IL_TZ,
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

/** "Thu 8 Oct, 23:30" in Israel time. */
export function formatIL(iso: string): string {
  return dateTime.format(new Date(iso))
}

function ilParts(date: Date): Record<string, number> {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: IL_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const out: Record<string, number> = {}
  for (const p of parts) if (p.type !== 'literal') out[p.type] = Number(p.value)
  return out
}

/** Offset of Israel time from UTC at an instant, in minutes (180 in summer, 120 in winter). */
export function ilOffsetMinutes(date: Date): number {
  const p = ilParts(date)
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second)
  return Math.round((asUtc - date.getTime()) / 60000)
}

function pad(n: number): string {
  return String(Math.abs(n)).padStart(2, '0')
}

/** A datetime-local value read as Israel wall time → ISO string with the right offset. */
export function ilLocalToIso(local: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(local)
  if (!m) throw new Error('expected YYYY-MM-DDTHH:MM')
  const [y, mo, d, h, mi] = m.slice(1).map(Number)
  const wall = Date.UTC(y, mo - 1, d, h, mi)
  let offset = ilOffsetMinutes(new Date(wall - 180 * 60000))
  offset = ilOffsetMinutes(new Date(wall - offset * 60000))
  const sign = offset >= 0 ? '+' : '-'
  return `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:00${sign}${pad(Math.trunc(offset / 60))}:${pad(offset % 60)}`
}

/** Now in Israel time as a datetime-local value ("2026-10-08T12:00"). */
export function nowILLocal(now: Date = new Date()): string {
  const p = ilParts(now)
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`
}

export function statusTone(status: Status): 'good' | 'warn' | 'bad' | 'muted' | 'info' {
  switch (status) {
    case 'QL':
      return 'good'
    case 'QL candidate':
      return 'info'
    case 'needs review':
      return 'warn'
    case 'disqualified':
    case 'suppressed':
      return 'bad'
    default:
      return 'muted'
  }
}

export function triIcon(tri: Tri): string {
  return tri === 'pass' ? '✔' : tri === 'fail' ? '✘' : '?'
}

export function stateLabel(state: AnswerState): string {
  return {
    owned: 'owned',
    mentioned_unowned: 'mentioned, not owned',
    absent: 'absent',
    wrong: 'wrong claim',
  }[state]
}

export function scoreLabel(score: number | null, band: string | null): string {
  if (score === null) return '—'
  return band && band !== 'nurture' ? `${score} · ${band}` : String(score)
}

export function sundayOf(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() - d.getUTCDay())
  return d.toISOString().slice(0, 10)
}

export function shiftWeek(sunday: string, weeks: number): string {
  const d = new Date(`${sunday}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 7 * weeks)
  return d.toISOString().slice(0, 10)
}
