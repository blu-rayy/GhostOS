import type { GhostOSPlatform } from './types'

/** Browser-development adapter: there is no folder access, so it returns a labelled mock folder only. */
export const browserPlatform: GhostOSPlatform = {
  capabilities: {
    runtime: 'browser',
    canSelectFolder: false,
    hasNativeFilesystem: false,
    isMockData: true,
  },
  async selectFolder() {
    return {
      kind: 'mock',
      name: 'Sample fixtures',
      documentCount: null,
    }
  },
}
