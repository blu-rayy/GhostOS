// Narrow, explicit bridge. Do not expose ipcRenderer, fs, shell or require.
// Shape must match ElectronBridge in src/platform/types.ts.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ghostos', {
  platform: process.platform,
  version: process.versions.electron,
  capabilities: { canSelectFolder: true, hasNativeFilesystem: false },
  /** Opens the native folder picker. Resolves to { name, path, documentCount } or null. */
  selectFolder: () => ipcRenderer.invoke('ghostos:select-folder'),
});
