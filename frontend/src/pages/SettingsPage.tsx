import { useState } from 'react'
import { Cpu, FlaskConical, Info, Lock, RotateCcw, Server, ShieldCheck, SlidersHorizontal, Wrench } from 'lucide-react'
import { ServiceRow } from '../components/shell/LocalStatusIndicator'
import { useServiceStates } from '../components/shell/useServiceStates'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { cx } from '../components/ui/cx'
import { KeyValue, PageHeader, Panel, PathText } from '../components/ui/Layout'
import { mockScenario } from '../api/mock'
import { formatDateTime } from '../lib/format'
import { useApp } from '../state/AppState'

function Switch({ checked, onChange, label, description, disabled }: { checked: boolean; onChange?: (v: boolean) => void; label: string; description?: string; disabled?: boolean }) {
  return (
    <label className={cx('flex items-start justify-between gap-4 py-2', disabled ? 'cursor-not-allowed' : 'cursor-pointer')}>
      <span>
        <span className="block text-sm">{label}</span>
        {description && <span className="block text-xs text-fg-muted">{description}</span>}
      </span>
      <span className="relative mt-0.5 shrink-0">
        <input type="checkbox" role="switch" className="peer sr-only" checked={checked} disabled={disabled} onChange={(e) => onChange?.(e.target.checked)} />
        <span
          className={cx(
            'block h-5 w-9 rounded-full border transition-colors duration-[120ms] peer-focus-visible:outline-2 peer-focus-visible:outline-accent',
            checked ? 'border-accent bg-accent' : 'border-line-strong bg-surface-3',
            disabled && 'opacity-60',
          )}
        />
        <span className={cx('absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform duration-[120ms]', checked ? 'translate-x-[18px]' : 'translate-x-0.5')} />
      </span>
    </label>
  )
}

export function SettingsPage() {
  const { state, dispatch, resetSession, platform, usingFixtures } = useApp()
  const svc = useServiceStates()
  const s = state.status
  // mockScenario is a plain module object; mirror it in local state so the switches re-render.
  const [scenario, setScenario] = useState({ ...mockScenario })
  const setFlag = (k: keyof typeof mockScenario, v: boolean) => {
    mockScenario[k] = v
    setScenario({ ...mockScenario })
  }

  return (
    <div className="scroll-area flex-1">
      <PageHeader title="Settings" breadcrumbs={['Settings']} description="Local processing status, limits and diagnostics." />
      <div className="grid grid-cols-2 gap-4 p-6">
        <Panel title="Local services" icon={Server}>
          <div className="space-y-2.5">
            <div className="rounded-md border border-line bg-surface-2/50 px-3 py-2">
              <ServiceRow name="GhostOS backend (FastAPI)" {...svc.backend} />
              <PathText className="text-fg-subtle">{s?.backend_endpoint ?? 'http://127.0.0.1:8000'}</PathText>
            </div>
            <div className="rounded-md border border-line bg-surface-2/50 px-3 py-2">
              <ServiceRow name="Ollama" {...svc.model} />
              <PathText className="text-fg-subtle">{s?.model_endpoint ?? 'http://127.0.0.1:11434'}</PathText>
            </div>
          </div>
          <div className="mt-3 divide-y divide-line">
            <KeyValue label="Model">{s ? <PathText>{s.model_name}</PathText> : '—'}</KeyValue>
            <KeyValue label="Last inference">{s?.last_inference_ms != null ? `${s.last_inference_ms} ms${s.last_inference_at ? ` · ${formatDateTime(s.last_inference_at)}` : ''}` : '—'}</KeyValue>
            <KeyValue label="External requests this session">
              <span className={svc.external > 0 ? 'font-semibold text-danger' : ''}>{s ? s.external_requests : '—'}</span>
            </KeyValue>
          </div>
          <p className="mt-3 flex items-start gap-1.5 text-xs text-fg-subtle">
            <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
            {usingFixtures ? 'Fixture mode: these values come from src/fixtures/status.json, not a live check.' : state.statusError ? `Last check failed: ${state.statusError}` : 'From GET /api/status.'}
          </p>
        </Panel>

        <Panel title="Privacy" icon={ShieldCheck}>
          <Switch checked disabled label="Local-only processing" description="Documents are analyzed on this device only." />
          <Switch checked={false} disabled label="Cloud model fallback" description="Not available. GhostOS never falls back to a remote AI provider." />
          <Switch checked={false} disabled label="Cloud sync" description="Not available in GhostOS." />
          <div className="mt-2 flex items-center gap-2 text-xs text-success">
            <Lock size={13} aria-hidden /> If the local model is unavailable, scans stop with an error instead of switching providers.
          </div>
        </Panel>

        <Panel title="Limits & file types" icon={SlidersHorizontal}>
          <div className="divide-y divide-line">
            <KeyValue label="Supported types">
              <span className="flex justify-end gap-1">
                {['PDF (text)', 'TXT', 'CSV'].map((t) => (
                  <Badge key={t}>{t}</Badge>
                ))}
              </span>
            </KeyValue>
            <KeyValue label="Files per scan">{state.scan?.max_files ?? 100}</KeyValue>
            <KeyValue label="Write scope">Selected folder only</KeyValue>
            <KeyValue label="Deletes">Never</KeyValue>
            <KeyValue label="Destination paths">Built by backend rules, not model output</KeyValue>
          </div>
        </Panel>

        <Panel title="Diagnostics" icon={Cpu}>
          <div className="divide-y divide-line">
            <KeyValue label="Runtime">{platform.capabilities.runtime === 'electron' ? `Electron ${platform.version ?? ''} · ${platform.os ?? ''}` : 'Browser (no desktop bridge)'}</KeyValue>
            <KeyValue label="Renderer isolation">{platform.capabilities.runtime === 'electron' ? 'Context isolation on · no Node access' : 'n/a in browser'}</KeyValue>
            <KeyValue label="Native folder picker">{platform.capabilities.canSelectFolder ? 'Available' : 'Not available'}</KeyValue>
            <KeyValue label="Data source">{usingFixtures ? 'Fixture mock (src/fixtures)' : 'FastAPI backend'}</KeyValue>
          </div>
        </Panel>

        <Panel title="Demo scenarios" icon={FlaskConical} className="col-span-2">
          <div className="grid grid-cols-2 gap-x-8">
            <div className="divide-y divide-line">
              <Switch
                checked={scenario.scanError}
                onChange={(v) => setFlag('scanError', v)}
                disabled={!usingFixtures}
                label="Fixture: scan fails halfway"
                description="The mock reports a model error during the next scan."
              />
              <Switch
                checked={scenario.undoConflict}
                onChange={(v) => setFlag('undoConflict', v)}
                disabled={!usingFixtures}
                label="Fixture: undo conflict"
                description="The mock reports one file whose original path is now taken."
              />
              <Switch
                checked={state.simulateActivityError}
                onChange={(v) => dispatch({ type: 'patch', patch: { simulateActivityError: v } })}
                label="Activity log failure"
                description="Shows the Activity screen's error state."
              />
            </div>
            <div className="flex flex-col justify-between gap-4 rounded-md border border-line bg-surface-2/50 p-4">
              <div className="flex gap-2 text-sm text-fg-muted">
                <Wrench size={16} className="mt-0.5 shrink-0" aria-hidden />
                For demos and testing only. The fixture switches only affect the mock backend and are disabled when talking to FastAPI.
              </div>
              <Button icon={RotateCcw} onClick={resetSession} className="self-start">
                Reset session
              </Button>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  )
}
