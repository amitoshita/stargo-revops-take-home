import { useState } from 'react'
import { api, ApiError } from '../lib/api'
import { ilLocalToIso } from '../lib/format'
import { href } from '../lib/route'
import type { LeadRow, PasteForm as Form } from '../lib/types'
import { Errors, StatusBadge } from './ui'

const CHANNELS = ['form_fill', 'email_reply', 'linkedin_dm', 'other']
const SOURCES = ['event-email', 'paid', 'historical-reactivation', 'new-connection', 'warm-network', 'organic/referral']

const EMPTY: Form = {
  from_name: '',
  from_email: '',
  linkedin_url: '',
  channel: 'email_reply',
  source: '',
  subject: '',
  body: '',
  received_at: '',
}

export function PasteForm({ onAdded }: { onAdded: () => void }) {
  const [form, setForm] = useState<Form>(EMPTY)
  const [errors, setErrors] = useState<string[] | null>(null)
  const [result, setResult] = useState<{ person_id: string; lead: LeadRow } | null>(null)
  const [busy, setBusy] = useState(false)

  const set = (key: keyof Form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setErrors(null)
    setResult(null)
    setBusy(true)
    try {
      const body = {
        from_name: form.from_name || null,
        from_email: form.from_email || null,
        linkedin_url: form.linkedin_url || null,
        channel: form.channel,
        source: form.source || null, // blank = source not recorded
        subject: form.subject || null,
        body: form.body,
        received_at: form.received_at ? ilLocalToIso(form.received_at) : null, // blank = now
      }
      const res = await api.post<{ person_id: string; lead: LeadRow }>('/inbound', body)
      setResult(res)
      setForm(EMPTY)
      onAdded()
    } catch (err) {
      setErrors(err instanceof ApiError ? err.reasons : ['could not reach the server'])
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form card" onSubmit={submit}>
      <h1>Paste a new inbound message</h1>
      <p className="muted small">
        Goes through the same pipeline as the seed data. Give an email or a LinkedIn URL (either
        may be blank, not both).
      </p>
      <label>
        Name
        <input value={form.from_name} onChange={set('from_name')} />
      </label>
      <label>
        Email
        <input type="email" value={form.from_email} onChange={set('from_email')} />
      </label>
      <label>
        LinkedIn URL
        <input value={form.linkedin_url} onChange={set('linkedin_url')} placeholder="https://linkedin.com/in/…" />
      </label>
      <label>
        Channel
        <select value={form.channel} onChange={set('channel')}>
          {CHANNELS.map((c) => (
            <option key={c} value={c}>
              {c.replace('_', ' ')}
            </option>
          ))}
        </select>
      </label>
      <label>
        Source
        <select value={form.source} onChange={set('source')}>
          <option value="">not recorded</option>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label>
        Received at (Israel time, blank = now)
        <input type="datetime-local" value={form.received_at} onChange={set('received_at')} />
      </label>
      <label>
        Subject
        <input value={form.subject} onChange={set('subject')} />
      </label>
      <label>
        Message text
        <textarea rows={6} value={form.body} onChange={set('body')} />
      </label>
      <button type="submit" disabled={busy}>
        {busy ? 'Analysing…' : 'Add message'}
      </button>
      <Errors reasons={errors} />
      {result && (
        <p className="ok">
          Added. <StatusBadge status={result.lead.status} /> owner {result.lead.owner ?? '—'} ·{' '}
          <a href={href({ view: 'lead', personId: result.person_id })}>open lead</a>
        </p>
      )}
    </form>
  )
}
