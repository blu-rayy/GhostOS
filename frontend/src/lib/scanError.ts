/**
 * Turns the scan's free-text error (ScanProgress.error) into a plain cause for the
 * "reading stopped" screen. The contract has no error code yet, so the kind is
 * inferred from keywords. TODO(Dev 1): replace with an `error_code` field.
 */
export type ScanErrorKind = 'ai' | 'folder' | 'other'

export interface ScanErrorInfo {
  kind: ScanErrorKind
  /** Ends the sentence "Pip stopped … because ___." */
  cause: string
  /** The original message, for the "details" disclosure. */
  detail: string
}

const AI = /ollama|local ai|\bmodel\b|not loaded|not responding|stopped responding|inference|11434/i
const FOLDER = /folder|directory|no such file|not found|permission|access is denied|cannot open|can't open|does not exist/i

export function describeScanError(message: string | null | undefined): ScanErrorInfo {
  const detail = (message ?? '').trim()
  if (AI.test(detail)) return { kind: 'ai', cause: "the local AI isn't answering", detail }
  if (FOLDER.test(detail)) return { kind: 'folder', cause: "the folder can't be opened", detail }
  return { kind: 'other', cause: 'something went wrong while reading', detail }
}
