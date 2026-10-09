import type { ElectronBridge, GhostOSPlatform } from './types'
import { browserPlatform } from './browser'

function getBridge(): ElectronBridge | undefined {
  return typeof window === 'undefined' ? undefined : window.ghostos
}

export const electronPlatform: GhostOSPlatform = {
  capabilities: {
    runtime: 'electron',
    canSelectFolder: Boolean(getBridge()?.capabilities.canSelectFolder),
    hasNativeFilesystem: Boolean(getBridge()?.capabilities.hasNativeFilesystem),
    isMockData: false,
  },
  version: getBridge()?.version,
  os: getBridge()?.platform,
  async selectFolder() {
    const bridge = getBridge()
    if (!bridge?.capabilities.canSelectFolder) return null
    const selection = await bridge.selectFolder()
    return selection ? { ...selection, kind: 'native' } : null
  },
}

export function resolvePlatform(): GhostOSPlatform {
  return getBridge() ? electronPlatform : browserPlatform
}
