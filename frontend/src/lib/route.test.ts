import { describe, expect, it } from 'vitest'
import { href, parseRoute } from './route'
import { reasonsFrom } from './api'

describe('routing', () => {
  it('parses views', () => {
    expect(parseRoute('')).toEqual({ view: 'leads' })
    expect(parseRoute('#/kpi')).toEqual({ view: 'kpi' })
    expect(parseRoute('#/leads/P-ab12')).toEqual({ view: 'lead', personId: 'P-ab12' })
    expect(parseRoute('#/nonsense')).toEqual({ view: 'leads' })
  })

  it('round-trips a lead link', () => {
    const route = { view: 'lead', personId: 'HS-1001' } as const
    expect(parseRoute(href(route))).toEqual(route)
  })
})

describe('api errors', () => {
  it('reads service reasons and FastAPI validation errors', () => {
    expect(reasonsFrom({ detail: ['invalid email address'] })).toEqual(['invalid email address'])
    expect(reasonsFrom({ detail: [{ msg: 'Field required' }] })).toEqual(['Field required'])
    expect(reasonsFrom({ detail: 'not found' })).toEqual(['not found'])
    expect(reasonsFrom(null)).toEqual([])
  })
})
