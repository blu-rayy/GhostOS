import { useEffect, useRef, useState } from 'react'
import './App.css'
import { api, USING_FIXTURES } from './api'
import type {
  BatchResult,
  DocumentCorrection,
  PlanPreview,
  ScanProgress,
  ScanResult,
  SystemStatus,
  UndoResult,
} from './types/api'
import { FolderSelect } from './components/FolderSelect'
import { PlanView } from './components/PlanView'
import { ReviewView } from './components/ReviewView'
import { StatusBar } from './components/StatusBar'
import { Stepper, type Step } from './components/Stepper'

const POLL_MS = 500
const STATUS_POLL_MS = 5000

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function App() {
  const [step, setStep] = useState<Step>('select')

  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)

  const [progress, setProgress] = useState<ScanProgress | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)
  const [scan, setScan] = useState<ScanResult | null>(null)

  const [plan, setPlan] = useState<PlanPreview | null>(null)
  const [planLoading, setPlanLoading] = useState(false)
  const [batch, setBatch] = useState<BatchResult | null>(null)
  const [undo, setUndo] = useState<UndoResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const pollTimer = useRef<number | undefined>(undefined)

  // Status bar: model, endpoint, external request count.
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const s = await api.getStatus()
        if (!alive) return
        setStatus(s)
        setStatusError(null)
      } catch (e) {
        if (alive) setStatusError(errorText(e))
      }
    }
    tick()
    const id = window.setInterval(tick, STATUS_POLL_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  useEffect(() => () => window.clearTimeout(pollTimer.current), [])

  const startScan = async (root: string) => {
    setScanError(null)
    setScan(null)
    setPlan(null)
    setBatch(null)
    setUndo(null)
    try {
      let p = await api.startScan(root)
      setProgress(p)
      const poll = async () => {
        try {
          p = await api.getScanProgress(p.scan_id)
          setProgress(p)
          if (p.state === 'running') {
            pollTimer.current = window.setTimeout(poll, POLL_MS)
          } else if (p.state === 'error') {
            setScanError(p.error ?? 'Unknown error')
          } else {
            setScan(await api.getScan(p.scan_id))
            setProgress(null)
            setStep('review')
          }
        } catch (e) {
          setProgress(null)
          setScanError(errorText(e))
        }
      }
      pollTimer.current = window.setTimeout(poll, POLL_MS)
    } catch (e) {
      setProgress(null)
      setScanError(errorText(e))
    }
  }

  const correctDocument = async (fileId: string, correction: DocumentCorrection) => {
    const updated = await api.correctDocument(fileId, correction)
    setScan((s) => s && { ...s, documents: s.documents.map((d) => (d.file_id === fileId ? updated : d)) })
    setPlan(null) // stale; rebuilt on next visit to the plan step
  }

  const openPlan = async () => {
    if (!scan) return
    setStep('plan')
    setActionError(null)
    if (plan || batch) return
    setPlanLoading(true)
    try {
      setPlan(await api.getPlan(scan.scan_id))
    } catch (e) {
      setActionError(errorText(e))
    } finally {
      setPlanLoading(false)
    }
  }

  const approve = async () => {
    if (!plan) return
    setBusy(true)
    setActionError(null)
    try {
      setBatch(await api.approvePlan(plan.plan_id))
    } catch (e) {
      setActionError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  const undoBatch = async () => {
    if (!batch) return
    setBusy(true)
    setActionError(null)
    try {
      setUndo(await api.undoBatch(batch.batch_id))
    } catch (e) {
      setActionError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  // Once a batch is committed, the scan's files have moved; editing would be misleading.
  const reachable = new Set<Step>(batch ? ['select', 'plan'] : scan ? ['select', 'review', 'plan'] : ['select'])

  const goTo = (s: Step) => (s === 'plan' ? openPlan() : setStep(s))

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            👻
          </span>
          GhostOS
        </div>
        <span className="muted small">Local file organizer and expense reports</span>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <Stepper current={step} reachable={reachable} onSelect={goTo} />
        </aside>

        <main className="content">
          {step === 'select' && <FolderSelect progress={progress} scanError={scanError} onScan={startScan} />}
          {step === 'review' && scan && (
            <ReviewView scan={scan} onCorrect={correctDocument} onContinue={openPlan} />
          )}
          {step === 'plan' && scan && (
            <PlanView
              root={scan.root}
              plan={plan}
              loading={planLoading}
              batch={batch}
              undo={undo}
              busy={busy}
              actionError={actionError}
              onBackToReview={() => setStep('review')}
              onApprove={approve}
              onUndo={undoBatch}
            />
          )}
        </main>
      </div>

      <StatusBar status={status} error={statusError} usingFixtures={USING_FIXTURES} />
    </div>
  )
}
