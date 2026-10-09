import type { SystemStatus } from '../types/api'

interface Props {
  status: SystemStatus | null
  error: string | null
  usingFixtures: boolean
}

export function StatusBar({ status, error, usingFixtures }: Props) {
  return (
    <footer className="status-bar" aria-label="System status">
      {error ? (
        <span className="status-item status-bad">● Backend unreachable: {error}</span>
      ) : !status ? (
        <span className="status-item muted">Connecting to local backend…</span>
      ) : (
        <>
          <span className={`status-item ${status.model_loaded ? 'status-good' : 'status-bad'}`}>
            ● {status.model_loaded ? 'Model loaded' : 'Model not loaded'}
          </span>
          <span className="status-item">
            Model <code>{status.model_name}</code>
          </span>
          <span className="status-item">
            Endpoint <code>{status.model_endpoint}</code>
          </span>
          <span className={`status-item ${status.external_requests === 0 ? 'status-good' : 'status-bad'}`}>
            {status.external_requests === 0
              ? 'No external requests'
              : `${status.external_requests} external requests`}
          </span>
          {status.last_inference_ms !== null && (
            <span className="status-item muted">Last inference {(status.last_inference_ms / 1000).toFixed(1)}s</span>
          )}
        </>
      )}
      {usingFixtures && <span className="status-item fixture-badge">Fixture data</span>}
    </footer>
  )
}
