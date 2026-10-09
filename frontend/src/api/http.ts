import type { GhostApi } from './client'

// Loopback only: the UI never talks to anything but the local FastAPI service.
const BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // non-JSON error body
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const httpApi: GhostApi = {
  getStatus: () => request('/api/status'),
  startScan: (root) => request('/api/scan', json({ root })),
  getScanProgress: (scanId) => request(`/api/scans/${scanId}/progress`),
  getScan: (scanId) => request(`/api/scans/${scanId}`),
  correctDocument: (fileId, correction) =>
    request(`/api/documents/${fileId}`, { method: 'PATCH', body: JSON.stringify(correction) }),
  getPlan: (scanId) => request(`/api/scans/${scanId}/plan`),
  approvePlan: (planId) => request(`/api/plans/${planId}/approve`, json({})),
  undoBatch: (batchId) => request(`/api/batches/${batchId}/undo`, json({})),
}
