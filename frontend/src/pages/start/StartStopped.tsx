import { PaperButton } from '../../components/paper/Button'
import { NumberedSteps } from '../../components/paper/NumberedSteps'
import { PageFooter } from '../../components/paper/PageFooter'
import { CardTitle, PaperCard } from '../../components/paper/PaperCard'
import { StickyNote } from '../../components/paper/StickyNote'
import { PipWithBubble } from '../../components/pip/Pip'
import { DEMO_FOLDER_NAME, PIP_LINES } from '../../lib/copy'
import { describeScanError } from '../../lib/scanError'
import { useApp } from '../../state/AppState'

const NUM = 'font-mono text-[17px]'

/** 1d · The reading stopped. Uses the real error; technical detail sits behind "details". */
export function StartStopped() {
  const { state, startScan, resetSession } = useApp()
  const err = describeScanError(state.scanError)
  const p = state.progress
  const total = p && p.files_total > 0 ? p.files_total : null
  const at = total ? Math.min(p!.files_processed + 1, total) : null
  const folderName = state.folder?.kind === 'mock' ? DEMO_FOLDER_NAME : state.folder?.name

  return (
    <>
      <div className="scroll-area flex flex-1 flex-col">
        <div className="mx-auto grid w-full max-w-[1280px] flex-1 grid-cols-[380px_minmax(0,1fr)] items-center gap-10 px-16 pb-[22px] pt-[34px]">
          <PipWithBubble mood="sigh" line={PIP_LINES.scanStopped} size={270} bubbleClassName="ml-[30px] self-start" tailOffset={60} />

          <div className="flex min-w-0 flex-col gap-5">
            <div>
              {folderName && <div className="truncate text-[20px] text-graphite">{folderName}</div>}
              <h1 className="m-0 font-display text-[52px] font-normal leading-none">The reading stopped.</h1>
            </div>

            <StickyNote tone="pink" alert tilt={-0.6} className="px-[22px] py-[18px] text-[21px] leading-[1.35]">
              <div>
                {at && total ? (
                  <>
                    Pip stopped at file <span className={NUM}>{at}</span> of <span className={NUM}>{total}</span> because {err.cause}.
                  </>
                ) : (
                  <>Pip couldn&apos;t start reading because {err.cause}.</>
                )}
              </div>
              <div className="mt-1.5">
                <b>Nothing was changed.</b> No files moved, and no plan was made.
              </div>
              {err.detail && (
                <details className="mt-2 text-[17px]">
                  <summary className="cursor-pointer underline underline-offset-4">details</summary>
                  <p className="m-0 mt-1 break-words font-mono text-[14px] leading-5">{err.detail}</p>
                </details>
              )}
            </StickyNote>

            <PaperCard variant="a" className="flex flex-col gap-2.5 px-6 py-[18px]">
              <CardTitle>how to fix it</CardTitle>
              {err.kind === 'ai' ? (
                <NumberedSteps
                  steps={[
                    <>
                      Open <b>Ollama</b> on this computer and wait until it says it&apos;s running.
                    </>,
                    <>
                      Press <span className="marker">Try again</span>. Pip starts the folder from the top.
                    </>,
                  ]}
                />
              ) : (
                <NumberedSteps
                  steps={[
                    <>
                      Press <span className="marker">Try again</span>. Pip starts the folder from the top.
                    </>,
                    'If it stops again, choose another folder.',
                  ]}
                />
              )}
              <div className="border-t-2 border-dashed border-[#cfcfcf] pt-2 text-[17px] text-[#555]">
                Still stuck? Settings shows whether the local AI and the model are running. GhostOS never switches to a cloud AI.
              </div>
            </PaperCard>
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
            Try again
          </PaperButton>
        }
      />
    </>
  )
}
