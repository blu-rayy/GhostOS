/**
 * User-facing wording, following the "Words we change" table in the UX
 * principles board. Keep plain words here so every screen says the same thing.
 */

export const STEP_LABELS = ['Start', 'Check', 'Totals', 'Done'] as const

export const WORDS = {
  needsReview: 'Check this',
  extracted: 'Ready',
  failed: "Couldn't read",
  skipped: 'Not supported',
  reviewed: 'Checked by you',
  duplicate: 'Duplicate',
  plan: 'Where files will go',
  destination: 'Goes to',
  evidenceFound: 'Found in the file',
  evidenceMissing: 'Not found in the file',
  undo: 'Put files back',
  demoData: 'Demo data',
  offline: 'Offline · on this computer',
  history: 'History',
  settings: 'Settings',
} as const

export const moveFiles = (n: number) => `Move ${n} ${n === 1 ? 'file' : 'files'}`
export const checkFirst = (n: number) => `Check ${n} ${n === 1 ? 'file' : 'files'} first`

/** Pip's lines (the joke). Always shown next to a plain factual line. */
export const PIP_LINES = {
  hello: 'hi. I sort your receipts. I never leave this computer. I never leave, period.',
  waiting: '…go on, pick a folder.',
  reading: (n: number) => `reading ${n} files. riveting. (still on this computer)`,
  suspicious: 'two totals disagree. which one did you actually pay?',
  done: (n: number) => `${n} files moved. report's ready. you're welcome.`,
  sigh: "couldn't read this one. nothing changed.",
  guard: 'offline. your files stay right here. so do I.',
  /** Start screen (step 1) versions, per docs/design/step1-start.md. */
  startReading: (n: number | null) => (n ? `reading ${n} files. riveting.` : 'reading. riveting.'),
  scanStopped: "*sigh*. that didn't work.",
  /** Totals screen (step 3) versions, per docs/design/step3-totals.md. */
  carrying: (n: number) => `carrying ${n} ${n === 1 ? 'file' : 'files'}. my back.`,
  refused: (k: number) => (k === 1 ? 'one of them refused to budge.' : k === 2 ? 'two of them refused to budge.' : k === 3 ? '3 of them refused to budge.' : 'a few of them refused to budge.'),
} as const

/** Name shown for the bundled sample folder (never presented as a real folder). */
export const DEMO_FOLDER_NAME = 'Demo files'
