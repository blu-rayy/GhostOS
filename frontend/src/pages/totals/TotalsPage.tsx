import { useApp } from '../../state/AppState'
import { PaperButton } from '../../components/paper/Button'
import { MoveProblems } from './MoveProblems'
import { MovingScreen } from './MovingScreen'
import { TotalsSummary } from './TotalsSummary'

/**
 * Step 3 · Totals (docs/design/step3-totals.md). Picks the state from the session:
 * 3a/3b before moving, 3c while approve is running, 3d when some files didn't move.
 * A move without failures goes straight to Done (handled in AppState.approve).
 */
export function TotalsPage() {
  const { state, navigate, reloadPlan } = useApp()
  // After approval, show exactly what was approved.
  const plan = state.approvedPlan ?? state.plan
  const folderName = state.folder?.name ?? 'your folder'

  if (state.busy === 'approve' && state.approvedPlan) {
    return <MovingScreen total={state.approvedPlan.operations.length} folderName={folderName} />
  }
  if (state.batch && state.batch.failed.length > 0 && state.approvedPlan && state.phase === 'organized') {
    return <MoveProblems batch={state.batch} plan={state.approvedPlan} folderName={folderName} />
  }
  if (plan) return <TotalsSummary plan={plan} />

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="m-0 font-display text-[42px] font-normal">Your totals</h1>
      {!state.scan ? (
        <>
          <p className="m-0 text-[19px]">Read a folder first. Totals come from the files Pip read.</p>
          <PaperButton variant="primary" onClick={() => navigate('dashboard')}>
            Go to Start
          </PaperButton>
        </>
      ) : state.planError ? (
        <>
          <p className="m-0 text-[19px]" role="alert">
            Couldn't get the totals: {state.planError}
          </p>
          <PaperButton variant="secondary" onClick={() => void reloadPlan()}>
            Try again
          </PaperButton>
        </>
      ) : (
        <p className="m-0 text-[19px]" role="status">
          Getting your totals…
        </p>
      )}
    </div>
  )
}
