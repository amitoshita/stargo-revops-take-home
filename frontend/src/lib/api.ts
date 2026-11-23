// Thin fetch wrapper. Errors carry the server's reasons (never message content).

export class ApiError extends Error {
  readonly status: number
  readonly reasons: string[]

  constructor(status: number, reasons: string[]) {
    super(reasons.join('; ') || `HTTP ${status}`)
    this.status = status
    this.reasons = reasons
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  const text = await response.text()
  const body: unknown = text ? JSON.parse(text) : null
  if (!response.ok) {
    throw new ApiError(response.status, reasonsFrom(body))
  }
  return body as T
}

export function reasonsFrom(body: unknown): string[] {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (Array.isArray(detail)) {
      return detail.map((d) =>
        typeof d === 'string' ? d : typeof d === 'object' && d && 'msg' in d ? String(d.msg) : '',
      )
    }
    if (typeof detail === 'string') return [detail]
  }
  return []
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
}
