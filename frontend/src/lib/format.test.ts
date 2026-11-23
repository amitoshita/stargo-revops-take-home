import { describe, expect, it } from 'vitest'
import {
  formatIL,
  ilLocalToIso,
  ilOffsetMinutes,
  nowILLocal,
  scoreLabel,
  shiftWeek,
  statusTone,
  sundayOf,
} from './format'

describe('Israel time', () => {
  it('shows a UTC timestamp in Israel time (IN-017: Thu 23:30, not 20:30)', () => {
    expect(formatIL('2026-10-08T20:30:00Z')).toBe('Thu 8 Oct, 23:30')
  })

  it('shows IN-018 on Friday although its UTC date is Thursday', () => {
    expect(formatIL('2026-10-08T21:30:00Z')).toBe('Fri 9 Oct, 00:30')
  })

  it('knows the offset on both sides of the 25 Oct 2026 change', () => {
    expect(ilOffsetMinutes(new Date('2026-10-08T12:00:00Z'))).toBe(180)
    expect(ilOffsetMinutes(new Date('2026-10-26T12:00:00Z'))).toBe(120)
  })

  it('turns an edited decided_at (Israel wall time) into ISO with the right offset', () => {
    expect(ilLocalToIso('2026-10-08T12:00')).toBe('2026-10-08T12:00:00+03:00')
    expect(ilLocalToIso('2026-10-27T09:15')).toBe('2026-10-27T09:15:00+02:00')
    expect(() => ilLocalToIso('8 Oct')).toThrow()
  })

  it('gives now as Israel wall time for the form default', () => {
    expect(nowILLocal(new Date('2026-10-08T21:30:00Z'))).toBe('2026-10-09T00:30')
  })
})

describe('labels', () => {
  it('maps statuses to tones', () => {
    expect(statusTone('QL')).toBe('good')
    expect(statusTone('needs review')).toBe('warn')
    expect(statusTone('suppressed')).toBe('bad')
    expect(statusTone('nurture')).toBe('muted')
  })

  it('shows unknown score as a dash, never 0', () => {
    expect(scoreLabel(null, null)).toBe('—')
    expect(scoreLabel(84, 'A')).toBe('84 · A')
    expect(scoreLabel(12, 'nurture')).toBe('12')
  })

  it('finds the Sunday of a week and moves by weeks', () => {
    expect(sundayOf('2026-10-08')).toBe('2026-10-04')
    expect(sundayOf('2026-10-04')).toBe('2026-10-04')
    expect(shiftWeek('2026-10-04', 1)).toBe('2026-10-11')
  })
})
