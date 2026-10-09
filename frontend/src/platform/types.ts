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
  /**
   * Desktop Pip (Windows desktop app only, behind the Settings toggle). Cosmetic and
   * best-effort: none of these affect the session, and failures are ignored.
   */
  desktopPip?: {
    /**
     * Open `root` in File Explorer and put Pip on screen over it. `randomFiles` (demo data only):
     * when the file being read isn't visible, Pip haunts a random visible file instead.
     */
    start: (root: string, options?: { randomFiles?: boolean }) => void
    /** The file the backend is reading now (relative path); Pip possesses its icon. */
    target: (relativePath: string) => void
    /** Pip waves and leaves; GhostOS comes back to the front. */
    stop: () => void
    /** After a move: Pip flies into `folder` inside the Explorer window on `root`. */
    intoFolder: (root: string, folder: string) => void
  }
}

/** Exact shape exposed by electron/preload.cjs as window.ghostos. Keep the two in sync. */
export type ElectronBridge = {
  platform: string
  version: string
  capabilities: { canSelectFolder: boolean; hasNativeFilesystem: boolean }
  selectFolder: () => Promise<{ name: string; path: string; documentCount: number | null } | null>
  pipToFolder?: (root: string, folder: string) => Promise<{ ok: boolean; reason?: string }>
  desktopPipStart?: (root: string, options?: { randomFiles?: boolean }) => Promise<{ ok: boolean; reason?: string }>
  desktopPipTarget?: (relativePath: string) => void
  desktopPipStop?: () => Promise<{ ok: boolean }>
}

declare global {
  interface Window {
    ghostos?: ElectronBridge
  }
}
