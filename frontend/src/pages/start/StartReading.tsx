import { PaperButton } from '../../components/paper/Button'
import { HatchProgress } from '../../components/paper/HatchProgress'
import { PageFooter } from '../../components/paper/PageFooter'
import { PaperCard } from '../../components/paper/PaperCard'
import { LockIcon } from '../../components/paper/icons'
import { PipWithBubble } from '../../components/pip/Pip'
import { DEMO_FOLDER_NAME, PIP_LINES } from '../../lib/copy'
import { useApp } from '../../state/AppState'

/**
 * 1c · Pip is reading. Only shows what ScanProgress actually reports: no time
 * estimate and no per-file results (the API has neither yet), and an
 * indeterminate bar while the total is unknown.
 */
export function StartReading() {
  const { state, navigate, resetSession } = useApp()
  const p = state.progress
  const finished = state.scan !== null && state.phase !== 'scanning'
  const total = finished ? state.scan!.documents.length : p && p.files_total > 0 ? p.files_total : null
  const done = finished ? total : (p?.files_processed ?? 0)
  const folderName = state.folder?.kind === 'mock' ? DEMO_FOLDER_NAME : state.folder?.name

  return (
    <>
      <div className="scroll-area flex flex-1 flex-col">
        <div className="mx-auto grid w-full max-w-[1280px] flex-1 grid-cols-[380px_minmax(0,1fr)] items-center gap-10 px-16 pb-[22px] pt-[30px]">
          <PipWithBubble mood="reading" line={PIP_LINES.startReading(total)} size={270} bubbleClassName="ml-[30px] self-start" tailOffset={60} />

          <div className="flex min-w-0 flex-col gap-[18px]">
            <div>
              {folderName && <div className="truncate text-[20px] text-graphite">{folderName}</div>}
              <h1 className="m-0 font-display text-[52px] font-normal leading-none">{finished ? 'All read.' : 'Reading your files…'}</h1>
            </div>

            <PaperCard variant="a" className="flex flex-col gap-2.5 px-6 py-[18px]" aria-label="Reading progress">
              <div className="text-[22px]">
                {total === null ? (
                  'reading files…'
                ) : (
                  <>
                    <span className="font-mono text-[26px] font-bold">{done}</span> of <span className="font-mono text-[20px]">{total}</span> files read
                  </>
                )}
              </div>
              <HatchProgress value={total === null ? null : (done ?? 0) / total} label="Reading progress" />
              <div className="min-h-6 text-[17px] text-[#444]">
                {!finished && p?.current_file && (
                  <>
                    now reading <span className="break-all font-mono text-[14px] text-ink">{p.current_file}</span>
                  </>
                )}
              </div>
            </PaperCard>
          </div>
        </div>
      </div>
      <PageFooter
        left={
          // Back here from Check after reading: offer a fresh start, as on 1b and 1d.
          finished ? (
            <PaperButton variant="link" onClick={resetSession}>
              ← choose another folder
            </PaperButton>
          ) : (
            <div className="flex items-center gap-4">
              <PaperButton variant="link" onClick={resetSession}>
                ← cancel reading
              </PaperButton>
              <span className="flex items-center gap-2 text-[17px] text-[#444]">
                <LockIcon size={19} crisp />
                Nothing moves while Pip reads.
              </span>
            </div>
          )
        }
        right={
          <PaperButton variant="primary" disabled={!finished} disabledReason="opens when reading is done" reasonId="check-files-reason" onClick={() => navigate('files')}>
            Check files →
          </PaperButton>
        }
      />
    </>
  )
}
