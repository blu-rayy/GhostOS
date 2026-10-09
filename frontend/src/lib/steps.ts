/**
 * The 4-step flow (Start → Check → Expenses → Done) mapped onto the app's views
 * and session phase. Pure functions only.
 */
import type { SessionPhase, View } from '../types/ui'

export type StepIndex = 0 | 1 | 2 | 3

export interface StepInfo {
  index: StepIndex
  /** View opened when the step is clicked. */
  view: View
}

export const STEPS: StepInfo[] = [
  { index: 0, view: 'dashboard' },
  { index: 1, view: 'files' },
  { index: 2, view: 'report' },
  { index: 3, view: 'completion' },
]

/** Which step a view belongs to; null for side panels (History, Settings). */
export function stepForView(view: View): StepIndex | null {
  switch (view) {
    case 'dashboard':
    case 'folder':
    case 'scanning':
      return 0
    case 'files':
    case 'plan':
      return 1
    case 'report':
      return 2
    case 'completion':
      return 3
    case 'activity':
    case 'settings':
      return null
  }
}

export interface StepContext {
  phase: SessionPhase
  hasScan: boolean
  hasApprovedPlan: boolean
}

/** A step is finished once the flow has moved past it (or the user is past it). */
export function isStepDone(i: StepIndex, ctx: StepContext, current: StepIndex | null = null): boolean {
  if (i === 0) return ctx.hasScan && ctx.phase !== 'scanning'
  if (i === 1) return ctx.hasApprovedPlan || (current !== null && current > 1)
  if (i === 2) return ctx.hasApprovedPlan
  return ctx.hasApprovedPlan && ctx.phase !== 'organizing'
}

/**
 * Whether a step in the tracker can be clicked. Only moves the current flow already
 * allows: Check ↔ Expenses while reviewing, Expenses ↔ Done after files moved. Start is
 * never reopened from the tracker once a scan exists.
 *
 * Temporary exception to "not clickable forward": Check → Expenses stays clickable
 * because the pre-redesign Check screens have no link to Expenses. Remove it when the
 * paper Check screen gets its own "next" action.
 */
export function canOpenStep(i: StepIndex, current: StepIndex | null, ctx: StepContext): boolean {
  if (i === current) return false
  if (ctx.hasApprovedPlan) return i === 2 || i === 3
  if (ctx.hasScan && ctx.phase === 'reviewing') return i === 1 || i === 2
  // Before a scan exists, Start is the only place to be (e.g. coming back from History).
  return i === 0
}
