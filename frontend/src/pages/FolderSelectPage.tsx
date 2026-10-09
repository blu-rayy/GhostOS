import { useState } from 'react'
import { Ban, Check, Database, FileText, FolderOpen, Info, Lock, Play, ShieldCheck, X } from 'lucide-react'
import { FixtureTag } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Banner, KeyValue, PageHeader, Panel, PathText } from '../components/ui/Layout'
import { errorText } from '../lib/format'
import { useApp } from '../state/AppState'

const MAX_FILES = 100
const SUPPORTED_TYPES = ['PDF (text-based)', 'TXT', 'CSV']

export function FolderSelectPage() {
  const { state, platform, chooseFolder, chooseSampleFolder, setTypedRoot, startScan, navigate, usingFixtures } = useApp()
  const [pickerError, setPickerError] = useState<string | null>(null)
  const folder = state.folder
  const scanning = state.phase === 'scanning'
  const canPick = platform.capabilities.canSelectFolder
  // Browser + real backend: the browser cannot read absolute paths, so the user types one.
  const needsTypedPath = folder?.kind === 'mock' && !usingFixtures

  async function pickNative() {
    setPickerError(null)
    try {
      await chooseFolder()
    } catch (e) {
      setPickerError(`The folder picker could not be opened: ${errorText(e)}`)
    }
  }

  return (
    <div className="scroll-area flex-1">
      <PageHeader
        title="Select a folder"
        breadcrumbs={['Dashboard', 'Select folder']}
        description="Choose the folder GhostOS should analyze. Selecting a folder starts nothing on its own."
        actions={
          <Button variant="ghost" onClick={() => navigate('dashboard')}>
            Cancel
          </Button>
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-4 p-6">
        <div className="space-y-4">
          <Panel>
            <div className="flex flex-col items-center rounded-md border border-dashed border-line-strong bg-surface-2/40 px-6 py-8 text-center">
              <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-accent/15 text-accent-hover">
                <FolderOpen size={22} aria-hidden />
              </div>
              <h2 className="text-base font-semibold">Choose a folder on this computer</h2>
              <p className="mt-1 max-w-md text-sm text-fg-muted">GhostOS looks at files in this folder and its subfolders, up to {MAX_FILES} files.</p>
              <div className="mt-4 flex gap-2">
                <Button variant="primary" icon={FolderOpen} onClick={pickNative} disabled={!canPick || scanning}>
                  Choose folder…
                </Button>
                {(usingFixtures || !canPick) && (
                  <Button icon={Database} onClick={chooseSampleFolder} disabled={scanning}>
                    Use sample folder
                  </Button>
                )}
              </div>
              {!canPick && <p className="mt-3 text-xs text-fg-subtle">The native folder picker is available in the GhostOS desktop app (Electron). In the browser you can use the sample folder.</p>}
            </div>
            {pickerError && (
              <Banner tone="danger" icon={X} className="mt-3">
                {pickerError}
              </Banner>
            )}
          </Panel>

          <Panel title="Selected folder" icon={FolderOpen}>
            {!folder ? (
              <p className="text-sm text-fg-subtle">No folder selected yet.</p>
            ) : (
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold">{folder.name}</span>
                  {folder.kind === 'mock' && <FixtureTag />}
                </div>
                <div className="mt-2 divide-y divide-line">
                  <KeyValue label="Location">
                    {folder.path ? <PathText>{folder.path}</PathText> : <span className="text-fg-muted">{usingFixtures ? 'Bundled fixtures, not a folder on disk' : 'Not chosen yet'}</span>}
                  </KeyValue>
                  <KeyValue label="Files found">{folder.documentCount ?? <span className="text-fg-muted">Counted during the scan</span>}</KeyValue>
                  <KeyValue label="Write scope">Only inside this folder</KeyValue>
                </div>
                {needsTypedPath && (
                  <label className="mt-3 block">
                    <span className="label">Folder path for the backend</span>
                    <input className="input mt-1 font-mono" placeholder="C:\Users\you\Documents\Receipts" value={state.typedRoot} onChange={(e) => setTypedRoot(e.target.value)} />
                  </label>
                )}
                {folder.kind === 'native' && usingFixtures && (
                  <Banner tone="warning" icon={Info} className="mt-3" title="Fixture mode">
                    The scan below uses the bundled fixtures. This folder's contents are not read until the app talks to the real backend (VITE_USE_FIXTURES=false).
                  </Banner>
                )}
              </div>
            )}
            {state.scanError && state.phase === 'folder_selected' && (
              <Banner tone="danger" icon={X} className="mt-3">
                {state.scanError}
              </Banner>
            )}
            <div className="mt-4 flex items-center justify-between gap-4 border-t border-line pt-4">
              <p className="flex items-center gap-2 text-xs text-fg-muted">
                <Lock size={13} aria-hidden />
                Scanning reads files only. It does not move, rename or delete anything.
              </p>
              <Button variant="primary" icon={Play} disabled={!folder || scanning} onClick={startScan}>
                Start scan
              </Button>
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="What selecting does" icon={ShieldCheck}>
            <ul className="space-y-2 text-sm">
              {(
                [
                  [true, 'Lets GhostOS read supported files in this folder'],
                  [true, 'Drafts a proposed organization plan'],
                  [false, 'Does not move or rename any file'],
                  [false, 'Does not delete anything, including duplicates'],
                  [false, 'Does not send documents off this device'],
                ] as const
              ).map(([ok, text]) => (
                <li key={text} className="flex gap-2">
                  {ok ? <Check size={15} className="mt-0.5 shrink-0 text-success" aria-hidden /> : <Ban size={15} className="mt-0.5 shrink-0 text-fg-subtle" aria-hidden />}
                  <span className={ok ? '' : 'text-fg-muted'}>{text}</span>
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Supported in this version" icon={FileText}>
            <ul className="space-y-1.5 text-sm">
              {SUPPORTED_TYPES.map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <Check size={14} className="text-success" aria-hidden />
                  {t}
                </li>
              ))}
            </ul>
            <div className="mt-3 border-t border-line pt-3 text-xs text-fg-muted">
              <p>Up to {MAX_FILES} files per scan. Symbolic links are never followed.</p>
              <p className="mt-1">Images, scanned PDFs, Word files and oversized files are listed but skipped.</p>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
