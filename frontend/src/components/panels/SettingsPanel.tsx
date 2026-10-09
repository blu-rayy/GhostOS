import { useState, type ReactNode } from 'react'
import { mockScenario } from '../../api/mock'
import { useApp } from '../../state/AppState'
import { formatDateTime } from '../../lib/format'
import { PaperButton } from '../paper/Button'
import { Chip, type ChipTone } from '../paper/Chip'
import { CardTitle, PaperCard } from '../paper/PaperCard'
import { useServiceStates, type ServiceState } from '../shell/useServiceStates'
import { cx } from '../ui/cx'

const TONE: Record<ServiceState, ChipTone> = { ok: 'done', down: 'oops', fixture: 'info', unknown: 'muted' }

/**
 * Settings panel: what is running locally (from GET /api/status, never presented as live in
 * demo mode), the privacy rules, limits, and the demo scenarios while demo data is in use.
 */
export function SettingsPanel() {
  const { state, resetSession, platform, usingFixtures } = useApp()
  const svc = useServiceStates()
  const s = state.status
  // mockScenario is a plain module object; mirror it in local state so the boxes re-render.
  const [scenario, setScenario] = useState({ ...mockScenario })
  const setFlag = (k: keyof typeof mockScenario, v: boolean) => {
    mockScenario[k] = v
    setScenario({ ...mockScenario })
  }

  return (
    <div className="space-y-5">
      <Section title="local AI">
        <Row label="GhostOS service" value={<Chip tone={TONE[svc.backend.state]} size="sm">{svc.backend.label}</Chip>} sub={s?.backend_endpoint ?? 'http://127.0.0.1:8000'} />
        <Row label="Ollama" value={<Chip tone={TONE[svc.model.state]} size="sm">{svc.model.label}</Chip>} sub={s?.model_endpoint ?? 'http://127.0.0.1:11434'} />
        <Row label="model" value={<span className="font-mono text-[14px]">{s?.model_name ?? '—'}</span>} />
        <Row label="last answer" value={s?.last_inference_ms != null ? `${s.last_inference_ms} ms${s.last_inference_at ? ` · ${formatDateTime(s.last_inference_at)}` : ''}` : '—'} />
        <Row
          label="outside requests"
          value={<span className={cx('font-mono text-[15px]', svc.external > 0 && 'rounded bg-hl-oops px-1')}>{s ? s.external_requests : '—'}</span>}
        />
        <p className="m-0 mt-2 text-[16px] text-graphite">
          {usingFixtures ? 'Demo data: these values are bundled with the app, not a live check.' : state.statusError ? `Last check didn't work: ${state.statusError}` : 'Checked with the local GhostOS service every 10 seconds.'}
        </p>
      </Section>

      <Section title="privacy">
        <ul className="m-0 list-none space-y-1.5 p-0 text-[17px]">
          <Tick>Files are read and sorted on this computer only.</Tick>
          <Tick>No cloud AI. If the local AI stops, GhostOS stops and tells you.</Tick>
          <Tick>No cloud sync.</Tick>
          <Tick>Moves stay inside the folder you chose. Nothing is deleted.</Tick>
        </ul>
      </Section>

      <Section title="limits">
        <Row label="file types" value="PDF (text), TXT, CSV" />
        <Row label="files per folder" value={String(state.scan?.max_files ?? 100)} />
        <Row label="file size" value="up to 10 MB each" />
        <Row label="where files go" value="set by GhostOS rules, never by the AI" />
      </Section>

      <Section title="this app">
        <Row label="running in" value={platform.capabilities.runtime === 'electron' ? `desktop app${platform.version ? ` · Electron ${platform.version}` : ''}` : 'browser'} />
        <Row label="folder picker" value={platform.capabilities.canSelectFolder ? 'available' : 'desktop app only'} />
        <Row label="data" value={usingFixtures ? 'demo data' : 'local GhostOS service'} />
      </Section>

      {usingFixtures && (
        <Section title="demo scenarios">
          <p className="m-0 mb-2 text-[16px] text-graphite">For demos and testing. They only change the demo data.</p>
          <Box checked={scenario.scanError} onChange={(v) => setFlag('scanError', v)} label="Reading stops halfway" sub="The local AI 'stops answering' during the next read." />
          <Box checked={scenario.moveFailures} onChange={(v) => setFlag('moveFailures', v)} label="Two files don't move" sub="The next Move reports two failed files." />
          <Box checked={scenario.undoConflict} onChange={(v) => setFlag('undoConflict', v)} label="One file can't go back" sub="Putting files back leaves one where it is." />
          <PaperButton variant="secondary" size="sm" className="mt-3" onClick={resetSession}>
            Start over
          </PaperButton>
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <PaperCard as="section" shadow="sm" className="px-4 pb-3 pt-2">
      <CardTitle size="sm">{title}</CardTitle>
      <div className="mt-1">{children}</div>
    </PaperCard>
  )
}

function Row({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="border-b-[1.5px] border-dashed border-pencil py-1.5 last:border-b-0">
      <div className="flex items-center justify-between gap-3 text-[17px]">
        <span className="text-graphite">{label}</span>
        <span className="text-right">{value}</span>
      </div>
      {sub && <div className="font-mono text-[13px] text-graphite">{sub}</div>}
    </div>
  )
}

function Tick({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span aria-hidden className="font-bold">
        ✓
      </span>
      <span>{children}</span>
    </li>
  )
}

function Box({ checked, onChange, label, sub }: { checked: boolean; onChange: (v: boolean) => void; label: string; sub: string }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-1.5">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-1 h-5 w-5 shrink-0 accent-[#1a1a1a]" />
      <span>
        <span className="block text-[17px]">{label}</span>
        <span className="block text-[16px] text-graphite">{sub}</span>
      </span>
    </label>
  )
}
