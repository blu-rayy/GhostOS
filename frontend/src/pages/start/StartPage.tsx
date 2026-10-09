import { useApp } from '../../state/AppState'
import { StartEmpty } from './StartEmpty'
import { StartFolder } from './StartFolder'
import { StartReading } from './StartReading'
import { StartStopped } from './StartStopped'

/**
 * Step 1 · Start. Picks one of the four designed states from the existing session
 * state (no separate state machine):
 *   1a nothing picked · 1b folder chosen · 1c reading · 1d reading stopped
 */
export function StartPage() {
  const { state } = useApp()
  if (state.phase === 'scanning') return <StartReading />
  if (state.phase === 'scan_failed') return <StartStopped />
  // A finished scan normally jumps straight to Check; if Start is shown again, keep the full bar.
  if (state.scan) return <StartReading />
  if (state.folder) return <StartFolder />
  return <StartEmpty />
}
