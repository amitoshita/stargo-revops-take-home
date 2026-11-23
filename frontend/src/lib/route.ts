// Minimal hash router: #/leads, #/leads/<id>, #/paste, #/kpi, #/geo.

export type Route =
  | { view: 'leads' }
  | { view: 'lead'; personId: string }
  | { view: 'paste' }
  | { view: 'kpi' }
  | { view: 'geo' }

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent)
  if (parts[0] === 'leads' && parts[1]) return { view: 'lead', personId: parts[1] }
  if (parts[0] === 'paste') return { view: 'paste' }
  if (parts[0] === 'kpi') return { view: 'kpi' }
  if (parts[0] === 'geo') return { view: 'geo' }
  return { view: 'leads' }
}

export function href(route: Route): string {
  return route.view === 'lead' ? `#/leads/${encodeURIComponent(route.personId)}` : `#/${route.view}`
}
