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
  // Cosmetic and best-effort: failures change nothing in the app. Windows only.
  desktopPip:
    getBridge()?.platform === 'win32' && getBridge()?.desktopPipStart
      ? {
          start: (root, options) => void getBridge()?.desktopPipStart?.(root, options).catch(() => undefined),
          target: (relativePath) => getBridge()?.desktopPipTarget?.(relativePath),
          stop: () => void getBridge()?.desktopPipStop?.().catch(() => undefined),
          intoFolder: (root, folder) => void getBridge()?.pipToFolder?.(root, folder).catch(() => undefined),
        }
      : undefined,
}

export function resolvePlatform(): GhostOSPlatform {
  return getBridge() ? electronPlatform : browserPlatform
}
