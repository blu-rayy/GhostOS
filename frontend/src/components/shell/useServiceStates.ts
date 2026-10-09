import { useApp } from '../../state/AppState'

export type ServiceState = 'unknown' | 'fixture' | 'ok' | 'down'

export interface ServiceLabel {
  state: ServiceState
  label: string
}

/** Derives honest service labels from GET /api/status. Fixture data is never presented as a live check. */
export function useServiceStates(): { backend: ServiceLabel; model: ServiceLabel; external: number } {
  const { state, usingFixtures } = useApp()
  const s = state.status
  if (usingFixtures) {
    return {
      backend: { state: 'fixture' as const, label: 'demo data' },
      model: { state: 'fixture' as const, label: s ? `${s.model_name} (demo data)` : 'demo data' },
      external: s?.external_requests ?? 0,
    }
  }
  if (state.statusError) {
    return { backend: { state: 'down' as const, label: 'Unreachable' }, model: { state: 'unknown' as const, label: 'Unknown' }, external: 0 }
  }
  if (!s) return { backend: { state: 'unknown' as const, label: 'Checking…' }, model: { state: 'unknown' as const, label: 'Checking…' }, external: 0 }
  return {
    backend: { state: 'ok' as const, label: 'Running' },
    model: s.model_loaded ? { state: 'ok' as const, label: `${s.model_name} loaded` } : { state: 'down' as const, label: 'Model not loaded' },
    external: s.external_requests,
  }
}

