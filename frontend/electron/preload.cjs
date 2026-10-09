// Narrow, explicit bridge. Do not expose ipcRenderer, fs, shell or require.
// Shape must match ElectronBridge in src/platform/types.ts.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ghostos', {
  platform: process.platform,
  version: process.versions.electron,
  capabilities: { canSelectFolder: true, hasNativeFilesystem: false },
  windowControls: {
    minimize: () => ipcRenderer.send('ghostos:window-minimize'),
    toggleMaximize: () => ipcRenderer.send('ghostos:window-toggle-maximize'),
    close: () => ipcRenderer.send('ghostos:window-close'),
  },
  /** Opens the native folder picker. Resolves to { name, path, documentCount } or null. */
  selectFolder: () => ipcRenderer.invoke('ghostos:select-folder'),
  /** Desktop Pip (Settings toggle, Windows only). Cosmetic; each resolves to { ok, reason? }. */
  pipToFolder: (root, folder) => ipcRenderer.invoke('ghostos:pip-to-folder', root, folder),
  desktopPipStart: (root, options) => ipcRenderer.invoke('ghostos:desktop-pip-start', root, options),
  desktopPipTarget: (relPath) => ipcRenderer.send('ghostos:desktop-pip-target', relPath),
  desktopPipProgress: (done, total) => ipcRenderer.send('ghostos:desktop-pip-progress', done, total),
  desktopPipStop: () => ipcRenderer.invoke('ghostos:desktop-pip-stop'),
});
