// Narrow, explicit bridge. Do not expose ipcRenderer, fs, shell or require.
// Shape must match ElectronBridge in src/platform/types.ts.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ghostos', {
  platform: process.platform,
  version: process.versions.electron,
  capabilities: { canSelectFolder: true, hasNativeFilesystem: false },
  /** Opens the native folder picker. Resolves to { name, path, documentCount } or null. */
  selectFolder: () => ipcRenderer.invoke('ghostos:select-folder'),
  /** Desktop Pip (Settings toggle, Windows only). Cosmetic; each resolves to { ok, reason? }. */
  pipToFolder: (root, folder) => ipcRenderer.invoke('ghostos:pip-to-folder', root, folder),
  desktopPipStart: (root) => ipcRenderer.invoke('ghostos:desktop-pip-start', root),
  desktopPipTarget: (relPath) => ipcRenderer.send('ghostos:desktop-pip-target', relPath),
  desktopPipStop: () => ipcRenderer.invoke('ghostos:desktop-pip-stop'),
});
