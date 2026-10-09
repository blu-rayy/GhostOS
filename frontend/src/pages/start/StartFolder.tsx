import { useState } from 'react'
import { PaperButton } from '../../components/paper/Button'
import { Chip } from '../../components/paper/Chip'
import { NumberedSteps } from '../../components/paper/NumberedSteps'
import { PageFooter } from '../../components/paper/PageFooter'
import { CardTitle, PaperCard } from '../../components/paper/PaperCard'
import { StickyNote } from '../../components/paper/StickyNote'
import { INK_FILTER_ID } from '../../components/pip/Pip'
import { DEMO_FOLDER_NAME } from '../../lib/copy'
import { errorText } from '../../lib/format'
import { useApp } from '../../state/AppState'

// These match what the scanner enforces (backend/app/services/scanner.py and
// orchestrator.py: .pdf/.txt/.csv, 100 files, 10 MB, symlinks skipped).
const READS = ['PDF with text', 'TXT', 'CSV']
const SKIPS = ['photos', 'Word files', 'scanned PDFs', 'files over 10 MB', 'shortcuts']

/** 1b · Folder chosen, not reading yet. */
export function StartFolder() {
  const { state, platform, usingFixtures, chooseFolder, setTypedRoot, startScan, resetSession } = useApp()
  const [pickerError, setPickerError] = useState<string | null>(null)
  const folder = state.folder!
  const isDemo = folder.kind === 'mock'
  const canPick = platform.capabilities.canSelectFolder
  // Browser + real backend: the browser can't read absolute paths, so the user types one.
  const needsTypedPath = isDemo && !usingFixtures

  async function change() {
    if (!canPick) return resetSession()
    setPickerError(null)
    try {
      await chooseFolder()
    } catch (e) {
      setPickerError(errorText(e))
    }
  }

  return (
    <>
      <div className="scroll-area flex flex-1 flex-col">
        <div className="mx-auto flex w-full max-w-[1280px] flex-1 flex-col gap-[22px] px-16 pb-6 pt-[34px]">
          <div>
            <div className="text-[20px] text-graphite">step 1 of 4</div>
            <h1 className="m-0 font-display text-[52px] font-normal leading-none">Ready when you are.</h1>
          </div>

          <div className="grid grid-cols-[1.25fr_1fr] items-start gap-7">
            <PaperCard as="section" variant="a" aria-label="Your folder" className="flex flex-col gap-[18px] px-7 py-6">
              <div className="flex items-center gap-4">
                <svg width="64" height="54" viewBox="0 0 64 54" aria-hidden focusable="false" className="shrink-0">
                  <g filter={`url(#${INK_FILTER_ID})`}>
                    <path d="M3 8h22l6 6h30v36H3Z" fill="#ffe066" stroke="#1a1a1a" strokeWidth="3" strokeLinejoin="round" />
                    <path d="M3 20h58" stroke="#1a1a1a" strokeWidth="3" />
                  </g>
                </svg>
                <div className="min-w-0 flex-1">
                  <div className="text-[18px] text-graphite">your folder</div>
                  <div className="truncate text-[32px] leading-[1.1]" title={folder.path ?? undefined}>
                    {isDemo ? DEMO_FOLDER_NAME : folder.name}
                  </div>
                </div>
                <PaperButton variant="link" onClick={change}>
                  change
                </PaperButton>
              </div>

              {needsTypedPath ? (
                <label className="flex flex-col gap-1 text-[17px]">
                  folder path on this computer
                  <input className="input font-mono text-data" placeholder="C:\Users\you\Documents\Receipts" value={state.typedRoot} onChange={(e) => setTypedRoot(e.target.value)} />
                </label>
              ) : (
                <div className="break-all rounded-[10px] border-2 border-dashed border-btn-shadow bg-path-box px-3 py-2 font-mono text-[14px] leading-5 text-[#333]">
                  {isDemo ? 'bundled demo files · not a folder on this computer' : folder.path}
                </div>
              )}
              {folder.kind === 'native' && usingFixtures && (
                <p className="m-0 -mt-2 text-[17px] text-[#444]">Demo mode: Pip reads the bundled demo files, not this folder.</p>
              )}

              <div className="flex flex-col gap-3 border-t-[2.5px] border-dashed border-ink pt-4">
                <CardTitle as="h2">what happens next</CardTitle>
                <NumberedSteps
                  steps={[
                    'Pip reads every supported file in this folder and its subfolders.',
                    "You check anything he isn't sure about.",
                    <>
                      Files only move when you press <span className="marker">Move files</span>. You can put them back.
                    </>,
                  ]}
                />
              </div>
            </PaperCard>

            <section className="flex flex-col gap-[18px]" aria-label="Which files Pip reads">
              <PaperCard variant="b" className="flex flex-col gap-2.5 px-6 py-5">
                <CardTitle as="h2">Pip reads</CardTitle>
                <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
                  {READS.map((t) => (
                    <li key={t}>
                      <Chip tone="done" size="lg">
                        {t}
                      </Chip>
                    </li>
                  ))}
                </ul>
                <CardTitle as="h3" size="sm" className="mt-1.5">
                  Pip skips (and tells you)
                </CardTitle>
                <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
                  {SKIPS.map((t) => (
                    <li key={t}>
                      <Chip tone="muted" size="lg">
                        {t}
                      </Chip>
                    </li>
                  ))}
                </ul>
                <div className="mt-1 text-[17px] text-[#555]">Up to 100 files per run.</div>
              </PaperCard>
              <StickyNote tone="yellow" tilt={-1} className="px-[18px] py-3.5 text-[19px] leading-[1.3]">
                Reading only looks. Nothing gets moved, renamed or deleted, and nothing leaves this computer.
              </StickyNote>
              {(pickerError || state.scanError) && (
                <StickyNote tone="pink" alert tilt={-0.6} className="px-[18px] py-3.5 text-[19px] leading-[1.3]">
                  {pickerError ? `The folder picker didn't open: ${pickerError}.` : state.scanError} Nothing was changed.
                </StickyNote>
              )}
            </section>
          </div>
        </div>
      </div>
      <PageFooter
        left={
          <PaperButton variant="link" onClick={resetSession}>
            ← choose another folder
          </PaperButton>
        }
        right={
          <PaperButton variant="primary" onClick={startScan}>
            Start reading →
          </PaperButton>
        }
      />
    </>
  )
}
