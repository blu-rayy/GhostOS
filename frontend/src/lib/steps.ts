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

/** Whether the user may jump to this step right now. */
export function canOpenStep(i: StepIndex, ctx: StepContext): boolean {
  if (i === 0) return true
  if (i === 1 || i === 2) return ctx.hasScan && ctx.phase !== 'scanning'
  return ctx.hasApprovedPlan
}

/** A step is finished once the flow has moved past it. */
export function isStepDone(i: StepIndex, ctx: StepContext): boolean {
  const moved = ctx.hasApprovedPlan && ctx.phase !== 'organizing'
  if (i === 0) return ctx.hasScan && ctx.phase !== 'scanning'
  if (i === 1 || i === 2) return ctx.hasApprovedPlan
  return moved
}
