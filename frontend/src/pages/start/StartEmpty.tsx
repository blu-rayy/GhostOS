import { useState } from 'react'
import { PaperButton } from '../../components/paper/Button'
import { PaperCard } from '../../components/paper/PaperCard'
import { StickyNote } from '../../components/paper/StickyNote'
import { CheckIcon, FolderIcon, LockIcon, SearchIcon } from '../../components/paper/icons'
import { PipWithBubble } from '../../components/pip/Pip'
import { PIP_LINES } from '../../lib/copy'
import { errorText } from '../../lib/format'
import { useApp } from '../../state/AppState'

const PROMISES = [
  { icon: SearchIcon, title: 'reads only', text: 'Reading never moves, renames or deletes anything.', variant: 'a' as const },
  { icon: CheckIcon, title: 'you decide', text: 'Nothing moves until you press “Move files”. You can put them back later.', variant: 'b' as const },
  { icon: LockIcon, title: 'stays here', text: 'No uploads, no cloud AI. The model runs on this computer.', variant: 'a' as const },
]

/** 1a · Nothing picked yet. */
export function StartEmpty() {
  const { platform, chooseFolder, chooseSampleFolder } = useApp()
  const [pickerError, setPickerError] = useState<string | null>(null)
  const canPick = platform.capabilities.canSelectFolder

  async function pick() {
    setPickerError(null)
    try {
      await chooseFolder()
    } catch (e) {
      setPickerError(errorText(e))
    }
  }

  return (
    <div className="scroll-area flex flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-[1280px] flex-1 flex-col justify-center gap-10 px-24 py-8">
        <div className="grid grid-cols-[minmax(0,1fr)_400px] items-center gap-10">
          <div className="flex flex-col gap-[18px]">
            <div className="text-[20px] text-graphite">step 1 of 4</div>
            <h1 className="m-0 font-display text-[64px] font-normal leading-[0.95]">Let&apos;s tidy a folder.</h1>
            <p className="m-0 max-w-[600px] text-[23px] leading-[1.35]">
              Pick the folder with your invoices and receipts. Pip reads them here, on this computer, and suggests where each one should go.
            </p>
            {canPick ? (
              <div className="mt-1.5 flex flex-wrap items-center gap-4">
                <PaperButton variant="primary" size="lg" onClick={pick}>
                  <FolderIcon size={24} crisp />
                  Choose folder…
                </PaperButton>
                <PaperButton variant="secondary" size="lg" onClick={chooseSampleFolder}>
                  try the demo files
                </PaperButton>
              </div>
            ) : (
              // Browser: no folder picker, so the demo files become the main action.
              <div className="mt-1.5 flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-4">
                  <PaperButton variant="primary" size="lg" onClick={chooseSampleFolder}>
                    try the demo files
                  </PaperButton>
                  <PaperButton variant="secondary" size="lg" disabled aria-describedby="pick-folder-reason">
                    <FolderIcon size={24} crisp />
                    Choose folder…
                  </PaperButton>
                </div>
                <p id="pick-folder-reason" className="m-0 text-[17px] text-graphite">
                  folder picking needs the desktop app
                </p>
              </div>
            )}
            <div className="text-[18px] text-[#555]">PDFs with text, TXT and CSV · up to 100 files · subfolders included</div>
            {pickerError && (
              <StickyNote tone="pink" alert tilt={-0.6} className="max-w-[600px] px-4 py-3 text-[18px]">
                The folder picker didn&apos;t open: {pickerError}. Nothing was changed.
              </StickyNote>
            )}
          </div>

          <PipWithBubble mood="waiting" line={PIP_LINES.waiting} size={250} bubbleClassName="mr-2.5 self-end" />
        </div>

        <ul className="m-0 grid list-none grid-cols-3 gap-[22px] p-0" aria-label="What GhostOS promises">
          {PROMISES.map((p) => (
            <PaperCard key={p.title} as="li" variant={p.variant} shadow="sm" className="flex items-start gap-3 px-[18px] py-3.5">
              <p.icon size={30} className="shrink-0" />
              <div>
                <div className="text-[21px] leading-7">{p.title}</div>
                <div className="text-[17px] leading-[1.3] text-[#444]">{p.text}</div>
              </div>
            </PaperCard>
          ))}
        </ul>
      </div>
    </div>
  )
}
