// GhostOS Electron main process (prototype).
// Security posture: the renderer gets NO Node.js or filesystem access.
// The privileged capabilities exposed (via preload) are a native folder picker that
// returns a path string, and the opt-in desktop Pip animation below. Nothing here
// reads, moves or deletes files.
const { app, BrowserWindow, desktopCapturer, dialog, ipcMain, screen, shell } = require('electron');
const { execFile } = require('node:child_process');
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
    frame: false,
    titleBarStyle: 'hidden',
    // Pip, rendered from public/pip.svg (Windows needs a PNG/ICO, not SVG).
    icon: path.join(__dirname, 'icon.png'),
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

ipcMain.on('ghostos:window-minimize', (event) => BrowserWindow.fromWebContents(event.sender)?.minimize());
ipcMain.on('ghostos:window-toggle-maximize', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) return;
  if (win.isMaximized()) win.unmaximize();
  else win.maximize();
});
ipcMain.on('ghostos:window-close', (event) => BrowserWindow.fromWebContents(event.sender)?.close());

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

/**
 * Desktop Pip (controlled demo, Windows only). Turned on by the user in Settings; the
 * renderer only calls these when that toggle is on. Purely cosmetic: the helper script
 * only reads window and icon positions, the snapshot is of icons already on screen, and
 * nothing here reads, moves or changes files. Any mismatch quietly does nothing.
 * Demo setup: icons visible in Explorer, no scrolling or window moving while Pip is out.
 *
 * - Reading: open the scanned folder in Explorer, then Pip "possesses" each file's icon
 *   as the backend reads it and wanders around carrying a box in between.
 * - After a move: bring that Explorer window forward and fly Pip into the folder that
 *   received the most files.
 */
const DESKTOP_PIP_OK = process.platform === 'win32';
const OVERLAY_HTML = path.join(__dirname, 'pip-overlay.html');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function findFolderWindow(root, target) {
  return new Promise((resolve) => {
    const child = execFile(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', path.join(__dirname, 'find-folder-window.ps1')],
      { env: { ...process.env, GHOSTOS_ROOT: root, GHOSTOS_TARGET: target }, timeout: 8000, windowsHide: true },
      (err, stdout) => {
        if (err) return resolve({ found: false, reason: err.message });
        try {
          resolve(JSON.parse(stdout.trim().split(/\r?\n/).pop()));
        } catch {
          resolve({ found: false, reason: 'unreadable helper output' });
        }
      },
    );
    child.stdin.end(); // PowerShell can wait on an open stdin pipe
  });
}

const validRoot = (root) => typeof root === 'string' && path.isAbsolute(root);
const dip = (r) => screen.screenToDipRect(null, r);
/** A DIP rect relative to the overlay (which covers exactly one display). */
const local = (r, origin) => ({ x: Math.round(r.x - origin.x), y: Math.round(r.y - origin.y), width: Math.round(r.width), height: Math.round(r.height) });

/** Transparent, click-through, always-on-top window over one display. No bridge, no network. */
function makeOverlay(bounds) {
  const overlay = new BrowserWindow({
    ...bounds,
    transparent: true,
    backgroundColor: '#00000000',
    frame: false,
    resizable: false,
    movable: false,
    focusable: false,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  overlay.setAlwaysOnTop(true, 'screen-saver');
  overlay.setIgnoreMouseEvents(true);
  overlay.webContents.on('will-navigate', (e) => e.preventDefault());
  overlay.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  return overlay;
}

/**
 * Snapshot each visible icon (taken before the overlay is shown) so Pip can lift and wobble a
 * copy, plus the background colour just inside its box to patch over the real one meanwhile.
 */
async function snapshotItems(items, display) {
  const phys = screen.dipToScreenRect(null, display.bounds);
  const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: phys.width, height: phys.height } });
  const src = sources.find((s) => s.display_id === String(display.id)) ?? sources[0];
  if (!src) return items.map(() => ({}));
  const img = src.thumbnail;
  const size = img.getSize();
  const k = size.width / phys.width;
  const bmp = img.toBitmap(); // BGRA
  return items.map((it) => {
    const r = { x: Math.round((it.x - phys.x) * k), y: Math.round((it.y - phys.y) * k), width: Math.round(it.width * k), height: Math.round(it.height * k) };
    if (r.x < 0 || r.y < 0 || r.width < 4 || r.height < 4 || r.x + r.width > size.width || r.y + r.height > size.height) return {};
    const i = ((r.y + 2) * size.width + (r.x + 2)) * 4;
    return { img: img.crop(r).toDataURL(), bg: `rgb(${bmp[i + 2]},${bmp[i + 1]},${bmp[i]})` };
  });
}

function bringToFront(win) {
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized()) win.restore();
  win.setAlwaysOnTop(true);
  win.show();
  win.focus();
  win.setAlwaysOnTop(false);
}

/** The reading session: one overlay that lives while the backend reads the folder. */
let session = null;

function overlayCall(s, js) {
  if (s?.overlay && !s.overlay.isDestroyed()) s.overlay.webContents.executeJavaScript(js).catch(() => undefined);
}

/**
 * Fallback: watch the Explorer window Pip is haunting. If it's minimized, moved, resized or
 * closed, Pip and the progress bar poof away and GhostOS comes forward, where its own
 * progress card keeps counting. The rest of the scan carries on without the overlay.
 */
function watchExplorer(s, hwnd) {
  if (!hwnd) return;
  const child = execFile(
    'powershell.exe',
    ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', path.join(__dirname, 'watch-folder-window.ps1')],
    { env: { ...process.env, GHOSTOS_HWND: String(hwnd) }, timeout: 16 * 60 * 1000, windowsHide: true },
    (err, stdout) => {
      if (s.watcher !== child) return; // stopped on purpose
      s.watcher = null;
      let event = null;
      try {
        event = JSON.parse(String(stdout).trim().split(/\r?\n/).pop()).event;
      } catch {
        return;
      }
      if (['closed', 'minimized', 'moved'].includes(event)) retireOverlay(s);
    },
  );
  child.stdin.end(); // PowerShell can wait on an open stdin pipe
  s.watcher = child;
}

function stopWatcher(s) {
  const child = s.watcher;
  s.watcher = null;
  if (child && child.exitCode === null) child.kill();
}

/** Pip and the bar vanish at once; GhostOS (and its in-app progress) comes to the front. */
function retireOverlay(s) {
  const overlay = s.overlay;
  if (!overlay || overlay.isDestroyed()) return;
  s.overlay = null; // later progress/targets now only update the app
  overlay.webContents.executeJavaScript('window.pipSession && window.pipSession.vanish()').catch(() => undefined);
  setTimeout(() => !overlay.isDestroyed() && overlay.close(), 600);
  if (!s.stopped) bringToFront(s.appWin);
}

async function stopSession(bringBack) {
  const s = session;
  session = null;
  if (!s) return;
  s.stopped = true;
  stopWatcher(s);
  if (s.overlay && !s.overlay.isDestroyed()) {
    overlayCall(s, 'window.pipSession && window.pipSession.stop()');
    const overlay = s.overlay;
    setTimeout(() => !overlay.isDestroyed() && overlay.close(), 1600);
  }
  if (bringBack) setTimeout(() => bringToFront(s.appWin), 1300);
}

ipcMain.handle('ghostos:desktop-pip-start', async (event, root, options) => {
  if (!DESKTOP_PIP_OK) return { ok: false, reason: 'Windows only' };
  if (!validRoot(root)) return { ok: false, reason: 'bad input' };
  await stopSession(false);
  const s = { appWin: BrowserWindow.fromWebContents(event.sender), overlay: null, pending: null, stopped: false };
  session = s;
  s.appWin?.once('closed', () => session === s && stopSession(false));

  const openError = await shell.openPath(root);
  if (openError) return { ok: false, reason: openError };
  // Wait for the Explorer window to appear and draw its icons.
  let found = null;
  for (let i = 0; i < 8 && !s.stopped; i++) {
    await sleep(i === 0 ? 900 : 500);
    found = await findFolderWindow(root, '');
    if (found.found && Array.isArray(found.items) && found.items.length > 0) break;
  }
  if (s.stopped) return { ok: false, reason: 'stopped' };
  if (!found?.found) return { ok: false, reason: found?.reason ?? 'no Explorer window' };

  const win = dip(found.window);
  const display = screen.getDisplayMatching(win);
  const raw = Array.isArray(found.items) ? found.items : found.items ? [found.items] : [];
  const shots = await snapshotItems(raw, display);
  if (s.stopped) return { ok: false, reason: 'stopped' };
  const items = raw.map((it, i) => ({ name: it.name, ...local(dip(it), display.bounds), ...shots[i] }));

  s.overlay = makeOverlay(display.bounds);
  await s.overlay.loadFile(OVERLAY_HTML);
  if (s.stopped) {
    s.overlay.close();
    return { ok: false, reason: 'stopped' };
  }
  s.overlay.showInactive();
  const randomFiles = Boolean(options && options.randomFiles);
  overlayCall(s, `window.pipSession.init(${JSON.stringify({ items, win: local(win, display.bounds), randomFiles })})`);
  if (s.pending) overlayCall(s, `window.pipSession.target(${JSON.stringify(s.pending)})`);
  if (s.progress) overlayCall(s, `window.pipSession.progress(${s.progress[0]}, ${s.progress[1]})`);
  watchExplorer(s, found.window.hwnd);
  return { ok: true, items: items.length };
});

// Fire-and-forget: the file the backend is reading now (relative path).
ipcMain.on('ghostos:desktop-pip-target', (_event, relPath) => {
  const s = session;
  if (!s || typeof relPath !== 'string' || relPath.length > 1024) return;
  s.pending = relPath;
  overlayCall(s, `window.pipSession.target(${JSON.stringify(relPath)})`);
});

// Fire-and-forget: reading progress for the bar inside the Explorer window.
ipcMain.on('ghostos:desktop-pip-progress', (_event, done, total) => {
  const s = session;
  if (!s || !Number.isInteger(done) || !Number.isInteger(total) || done < 0 || total < 0) return;
  s.progress = [Math.min(done, total || done), total];
  overlayCall(s, `window.pipSession.progress(${s.progress[0]}, ${s.progress[1]})`);
});

ipcMain.handle('ghostos:desktop-pip-stop', async () => {
  await stopSession(true);
  return { ok: true };
});

ipcMain.handle('ghostos:pip-to-folder', async (event, root, target) => {
  if (!DESKTOP_PIP_OK) return { ok: false, reason: 'Windows only' };
  // Only an absolute path and a single folder name, as produced by the app itself.
  if (!validRoot(root) || typeof target !== 'string' || !target || /[\\/]/.test(target)) {
    return { ok: false, reason: 'bad input' };
  }
  const appWin = BrowserWindow.fromWebContents(event.sender);
  if (!appWin) return { ok: false, reason: 'no window' };

  const found = await findFolderWindow(root, target);
  if (!found.found) return { ok: false, reason: found.reason };
  // If Windows refused to bring Explorer forward (the user clicked another app during the
  // move), Pip would dive into whatever window covers it. Skip instead.
  if (!found.raised) return { ok: false, reason: 'Explorer could not be brought to the front' };
  // Physical pixels -> DIP. Fall back to the middle of the window if the icon isn't visible.
  const win = dip(found.window);
  const box = found.item ? dip(found.item) : { x: win.x + win.width / 2 - 50, y: win.y + win.height / 2 - 50, width: 100, height: 100 };

  const display = screen.getDisplayMatching(box).bounds;
  const from = appWin.getContentBounds();
  const t = local(box, display);
  const query = {
    // Start at Pip's spot on the Done screen (left column), in overlay coordinates.
    sx: String(Math.round(from.x + Math.min(240, from.width / 4) - display.x)),
    sy: String(Math.round(from.y + from.height * 0.55 - display.y)),
    tx: String(t.x),
    ty: String(t.y),
    tw: String(t.width),
    th: String(t.height),
  };

  const overlay = makeOverlay(display);
  const closeLater = setTimeout(() => !overlay.isDestroyed() && overlay.close(), 6000);
  overlay.on('closed', () => clearTimeout(closeLater));
  await overlay.loadFile(OVERLAY_HTML, { query });
  overlay.showInactive();
  return { ok: true, onIcon: Boolean(found.item) };
});

// Own taskbar identity on Windows, so the window shows Pip instead of grouping under Electron.
if (process.platform === 'win32') app.setAppUserModelId('com.ghostos.app');

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
