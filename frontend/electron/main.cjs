// GhostOS Electron main process (prototype).
// Security posture: the renderer gets NO Node.js or filesystem access.
// The only privileged capability exposed (via preload) is a native folder picker
// that returns a path string. Nothing here reads, moves or deletes files.
const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const path = require('node:path');

const DEV_URL = process.env.VITE_DEV_SERVER_URL;

function createWindow() {
  const win = new BrowserWindow({
    width: 1366,
    height: 768,
    minWidth: 1100,
    minHeight: 640,
    backgroundColor: '#0e1117',
    title: 'GhostOS',
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  win.once('ready-to-show', () => win.show());

  // Block in-app navigation to anything other than the app itself.
  win.webContents.on('will-navigate', (event, url) => {
    const allowed = DEV_URL ? url.startsWith(DEV_URL) : url.startsWith('file://');
    if (!allowed) event.preventDefault();
  });
  // Never open new Electron windows; send external links to the OS browser only if https.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });

  if (DEV_URL) {
    win.loadURL(DEV_URL);
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
}

// Native folder picker. Returns { name, path, documentCount } or null — strings only.
// The renderer cannot list, read or write anything with it; the local FastAPI
// backend does the scanning. documentCount stays null until the backend reports it.
ipcMain.handle('ghostos:select-folder', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  const result = await dialog.showOpenDialog(win, {
    title: 'Select a folder for GhostOS to analyze',
    buttonLabel: 'Analyze this folder',
    properties: ['openDirectory', 'dontAddToRecent'],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  const folderPath = result.filePaths[0];
  return { name: path.basename(folderPath) || folderPath, path: folderPath, documentCount: null };
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
