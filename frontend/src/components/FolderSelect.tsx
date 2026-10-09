import { useState } from 'react'
import type { ScanProgress } from '../types/api'

const RECENTS_KEY = 'ghostos.recentRoots'
const DEFAULT_RECENTS = ['C:/Users/demo/Desktop/Unsorted Paperwork']

function loadRecents(): string[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY)
    return raw ? (JSON.parse(raw) as string[]) : DEFAULT_RECENTS
  } catch {
    return DEFAULT_RECENTS
  }
}

function saveRecent(root: string) {
  try {
    const next = [root, ...loadRecents().filter((r) => r !== root)].slice(0, 5)
    localStorage.setItem(RECENTS_KEY, JSON.stringify(next))
  } catch {
    // storage unavailable; recents are a convenience only
  }
}

// Browsers can't hand us an absolute path, so the user types/pastes it and the
// backend resolves and validates it.
function isAbsolutePath(p: string): boolean {
  return /^[a-zA-Z]:[\\/]/.test(p) || p.startsWith('/')
}

interface Props {
  progress: ScanProgress | null
  scanError: string | null
  onScan: (root: string) => void
}

export function FolderSelect({ progress, scanError, onScan }: Props) {
  const [recents] = useState(loadRecents)
  const [root, setRoot] = useState(recents[0] ?? '')
  const scanning = progress?.state === 'running'
  const trimmed = root.trim()
  const valid = isAbsolutePath(trimmed)

  const submit = () => {
    if (!valid || scanning) return
    saveRecent(trimmed)
    onScan(trimmed)
  }

  const pct = progress && progress.files_total > 0 ? (progress.files_processed / progress.files_total) * 100 : 0

  return (
    <section className="panel folder-select">
      <h1>Organize a folder</h1>
      <p className="lede">
        GhostOS reads PDF, TXT and CSV files on this computer, sorts out invoices and receipts, and drafts an
        expense report. Nothing moves until you approve the plan, and you can undo the whole batch.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        className="folder-form"
      >
        <label htmlFor="root">Folder path</label>
        <div className="folder-row">
          <input
            id="root"
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            placeholder="C:\Users\you\Desktop\Receipts"
            spellCheck={false}
            disabled={scanning}
          />
          <button type="submit" className="btn btn-primary" disabled={!valid || scanning}>
            {scanning ? 'Scanning…' : 'Scan'}
          </button>
        </div>
        {trimmed && !valid && <p className="field-error">Enter a full path, such as C:\Users\you\Documents\Receipts.</p>}
        {scanError && <p className="field-error">Scan failed: {scanError}</p>}

        {recents.length > 0 && (
          <div className="recents">
            <span className="muted">Recent:</span>
            {recents.map((r) => (
              <button type="button" key={r} className="chip" onClick={() => setRoot(r)} disabled={scanning}>
                {r}
              </button>
            ))}
          </div>
        )}
      </form>

      {progress && progress.state === 'running' && (
        <div className="scan-progress" role="status" aria-live="polite">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <p>
            Reading {progress.files_processed} of {progress.files_total} files
            {progress.current_file && (
              <>
                {' '}
                · <code>{progress.current_file}</code>
              </>
            )}
          </p>
        </div>
      )}

      <ul className="limits muted">
        <li>Scans up to 100 PDF (with text), TXT and CSV files. Other files are listed as skipped, with the reason.</li>
        <li>Files never leave this computer. Analysis runs on the local model shown in the status bar.</li>
        <li>GhostOS never deletes files, never follows symbolic links and never writes outside the chosen folder.</li>
      </ul>
    </section>
  )
}
