export type FolderSelection = {
  kind: 'mock' | 'native'
  name: string
  /** Absolute path, only when chosen with the native picker. Never shown as if real in mock mode. */
  path?: string
  /** Unknown until the backend scans the folder. */
  documentCount: number | null
}

export type PlatformCapabilities = {
  runtime: 'browser' | 'electron'
  canSelectFolder: boolean
  hasNativeFilesystem: boolean
  isMockData: boolean
}

export type GhostOSPlatform = {
  capabilities: PlatformCapabilities
  /** Electron version when running in the desktop shell. */
  version?: string
  /** OS platform string from Electron (win32, darwin, linux). */
  os?: string
  selectFolder: () => Promise<FolderSelection | null>
}

/** Exact shape exposed by electron/preload.cjs as window.ghostos. Keep the two in sync. */
export type ElectronBridge = {
  platform: string
  version: string
  capabilities: { canSelectFolder: boolean; hasNativeFilesystem: boolean }
  selectFolder: () => Promise<{ name: string; path: string; documentCount: number | null } | null>
}

declare global {
  interface Window {
    ghostos?: ElectronBridge
  }
}
