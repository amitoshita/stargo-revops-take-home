import { useEffect, useState } from 'react'
import { GeoView } from './components/GeoView'
import { KpiView } from './components/KpiView'
import { LeadDetailView } from './components/LeadDetail'
import { LeadQueue } from './components/LeadQueue'
import { ModeBanner } from './components/ModeBanner'
import { PasteForm } from './components/PasteForm'
import { Errors, Loading } from './components/ui'
import { href, parseRoute, type Route } from './lib/route'
import type { ContentBrief, GeoReport, KpiPack, LeadDetail, LeadRow, Mode } from './lib/types'
import { useApi } from './lib/useApi'

const WEEK_UNDER_REVIEW = '2026-10-04'

function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return route
}

const NAV: [Route['view'], string][] = [
  ['leads', 'Leads'],
  ['paste', 'Paste message'],
  ['kpi', 'KPI pack'],
  ['geo', 'AI visibility'],
]

export default function App() {
  const route = useRoute()
  const mode = useApi<Mode>('/mode')
  return (
    <div className="app">
      <header className="top">
        <strong className="brand">Stargo RevOps</strong>
        <nav>
          {NAV.map(([view, label]) => (
            <a
              key={view}
              href={href({ view } as Route)}
              className={route.view === view || (view === 'leads' && route.view === 'lead') ? 'active' : ''}
            >
              {label}
            </a>
          ))}
        </nav>
      </header>
      <ModeBanner mode={mode.data} />
      <main>
        <Page route={route} />
      </main>
    </div>
  )
}

function Page({ route }: { route: Route }) {
  switch (route.view) {
    case 'lead':
      return <LeadPage personId={route.personId} />
    case 'paste':
      return <PasteForm onAdded={() => undefined} />
    case 'kpi':
      return <KpiPage />
    case 'geo':
      return <GeoPage />
    default:
      return <LeadsPage />
  }
}

function LeadsPage() {
  const leads = useApi<LeadRow[]>('/leads')
  return (
    <section className="card">
      <h1>Lead queue</h1>
      <Errors reasons={leads.error} />
      {leads.loading && !leads.data ? <Loading /> : leads.data && <LeadQueue rows={leads.data} />}
    </section>
  )
}

function LeadPage({ personId }: { personId: string }) {
  const detail = useApi<LeadDetail>(`/leads/${encodeURIComponent(personId)}`)
  return (
    <>
      <p>
        <a href={href({ view: 'leads' })}>← Lead queue</a>
      </p>
      <Errors reasons={detail.error} />
      {detail.data ? <LeadDetailView detail={detail.data} onChange={detail.reload} /> : !detail.error && <Loading />}
    </>
  )
}

function KpiPage() {
  const [week, setWeek] = useState(WEEK_UNDER_REVIEW)
  const pack = useApi<KpiPack>(`/kpi?week=${week}`)
  return (
    <>
      <Errors reasons={pack.error} />
      {pack.data ? <KpiView pack={pack.data} week={week} onWeek={setWeek} /> : !pack.error && <Loading />}
    </>
  )
}

function GeoPage() {
  const report = useApi<GeoReport>('/geo')
  const brief = useApi<ContentBrief>('/geo/brief')
  return (
    <>
      <Errors reasons={report.error ?? brief.error} />
      {report.data ? (
        <GeoView report={report.data} brief={brief.data} onBrief={brief.reload} />
      ) : (
        !report.error && <Loading />
      )}
    </>
  )
}
