import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from './api'

export interface Loaded<T> {
  data: T | null
  error: string[] | null
  loading: boolean
  reload: () => void
}

/** GET a path; re-fetches when the path changes or reload() is called. */
export function useApi<T>(path: string | null): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; error: string[] | null; key: string }>({
    data: null,
    error: null,
    key: '',
  })
  const [tick, setTick] = useState(0)
  const key = `${path}#${tick}`

  useEffect(() => {
    if (path === null) return
    let live = true
    api
      .get<T>(path)
      .then((data) => live && setState({ data, error: null, key }))
      .catch((err: unknown) => {
        const reasons = err instanceof ApiError ? err.reasons : ['could not reach the server']
        if (live) setState({ data: null, error: reasons.length ? reasons : ['request failed'], key })
      })
    return () => {
      live = false
    }
  }, [path, key])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data: state.data, error: state.error, loading: state.key !== key, reload }
}
