'use strict';
const path = require('path');
const {
  app, BrowserWindow, ipcMain, globalShortcut, screen, Tray, Menu, nativeImage,
} = require('electron');
const config = require('./config');
const { Interaction } = require('./interaction');
const { createProvider } = require('./providers');

const SIZE_COMPACT = { width: 420, height: 92 };
const SIZE_PICKER = { width: 420, height: 480 };
const POLL_MS = 30 * 1000;

let cfg;
let provider;
let overlay;
let settingsWin;
let tray;
let current = null;
let pickerOpen = false;
let hook = null;

if (!app.requestSingleInstanceLock()) {
  app.quit();
}

const interaction = new Interaction(applyInteractive);

/* ---------------- Overlay-Fenster ---------------- */
function defaultBounds() {
  const wa = screen.getPrimaryDisplay().workArea;
  return { x: wa.x + wa.width - SIZE_COMPACT.width - 24, y: wa.y + 24, ...SIZE_COMPACT };
}

function onSomeScreen(b) {
  return screen.getAllDisplays().some(d => {
    const a = d.workArea;
    return b.x < a.x + a.width - 40 && b.x + 40 > a.x && b.y < a.y + a.height - 40 && b.y + 20 > a.y;
  });
}

function createOverlay() {
  let b = cfg.bounds && onSomeScreen(cfg.bounds) ? { ...cfg.bounds, ...SIZE_COMPACT } : defaultBounds();
  overlay = new BrowserWindow({
    ...b,
    frame: false,
    transparent: true,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    alwaysOnTop: true,
    focusable: false,
    show: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  overlay.setAlwaysOnTop(true, 'screen-saver');
  overlay.setVisibleOnAllWorkspaces(true);
  overlay.setIgnoreMouseEvents(true, { forward: true });
  overlay.loadFile(path.join(__dirname, 'renderer', 'overlay.html'));
  overlay.once('ready-to-show', () => overlay.showInactive());
  overlay.on('moved', () => {
    const [x, y] = overlay.getPosition();
    cfg.bounds = { x, y };
    config.save(cfg);
  });
}

function resizeOverlay(size) {
  if (!overlay) return;
  const [x, y] = overlay.getPosition();
  const wa = screen.getDisplayNearestPoint({ x, y }).workArea;
  // Ausklappen nach unten; reicht der Platz nicht, nach oben verschieben.
  const ny = Math.min(y, wa.y + wa.height - size.height);
  overlay.setBounds({ x, y: Math.max(wa.y, ny), width: size.width, height: size.height });
}

function cursorInside() {
  if (!overlay) return false;
  const p = screen.getCursorScreenPoint();
  const b = overlay.getBounds();
  return p.x >= b.x && p.x < b.x + b.width && p.y >= b.y && p.y < b.y + b.height;
}

function applyInteractive(on) {
  if (!overlay) return;
  overlay.setIgnoreMouseEvents(!on, { forward: true });
  overlay.setFocusable(on);
  send('interactive', { on, pinned: interaction.pinned });
  if (on) refreshCurrent();
  updateTray();
}

setInterval(() => {
  if (interaction.interactive) interaction.cursor(cursorInside());
}, 150);

/* ---------------- Strg-Erkennung ---------------- */
function startHook() {
  if (!cfg.ctrlHold || hook) return;
  try {
    const { uIOhook, UiohookKey } = require('uiohook-napi');
    const ctrl = new Set([UiohookKey.Ctrl, UiohookKey.CtrlRight]);
    uIOhook.on('keydown', e => {
      if (ctrl.has(e.keycode)) interaction.ctrlDown();
      else interaction.otherKey();
    });
    uIOhook.on('keyup', e => {
      if (ctrl.has(e.keycode)) interaction.ctrlUp(cursorInside());
    });
    uIOhook.start();
    hook = uIOhook;
  } catch (err) {
    console.error('Strg-Erkennung nicht verfügbar:', err.message);
    hook = null;
  }
}

function stopHook() {
  if (!hook) return;
  try { hook.stop(); hook.removeAllListeners(); } catch { /* egal */ }
  hook = null;
}

function registerShortcut() {
  globalShortcut.unregisterAll();
  if (!cfg.toggleShortcut) return;
  try {
    globalShortcut.register(cfg.toggleShortcut, () => interaction.togglePin());
  } catch (err) {
    console.error('Shortcut ungültig:', cfg.toggleShortcut, err.message);
  }
}

/* ---------------- Timer-Zustand ---------------- */
function send(ch, payload) {
  if (overlay && !overlay.isDestroyed()) overlay.webContents.send(ch, payload);
}

async function refreshCurrent() {
  try {
    current = await provider.getCurrent();
    send('current', current);
  } catch (err) {
    send('error', err.message);
  }
}

function remember(entry) {
  if (!entry || !entry.projectId || !entry.activityId) return;
  const key = entry.projectId + '|' + entry.activityId;
  const list = (cfg.recent || []).filter(r => r.projectId + '|' + r.activityId !== key);
  list.unshift({
    projectId: entry.projectId, projectName: entry.projectName,
    activityId: entry.activityId, activityName: entry.activityName,
  });
  cfg.recent = list.slice(0, 6);
  config.save(cfg);
}

function applyConfig() {
  provider = createProvider(cfg);
  current = null;
  registerShortcut();
  stopHook();
  startHook();
  app.setLoginItemSettings({ openAtLogin: !!cfg.autostart });
  send('config', config.publicView(cfg));
  refreshCurrent();
}

/* ---------------- IPC Overlay ---------------- */
ipcMain.handle('state:get', () => ({
  current,
  config: config.publicView(cfg),
  provider: provider.label,
  interactive: interaction.interactive,
  pinned: interaction.pinned,
}));

ipcMain.handle('projects:list', (_e, opts) => provider.listProjects(opts || {}));
ipcMain.handle('activities:list', (_e, id, opts) => provider.listActivities(id, opts || {}));

ipcMain.handle('timer:start', async (_e, sel) => {
  current = await provider.start(sel);
  if (current) {
    current.projectName = current.projectName && current.projectName !== 'ohne Liste'
      ? current.projectName : (sel.projectName || current.projectName);
    remember(current);
  }
  send('current', current);
  return current;
});

ipcMain.handle('timer:stop', async () => {
  await provider.stop();
  current = null;
  send('current', current);
  return null;
});

ipcMain.handle('timer:refresh', () => refreshCurrent());

ipcMain.on('picker:set', (_e, open) => {
  pickerOpen = !!open;
  resizeOverlay(pickerOpen ? SIZE_PICKER : SIZE_COMPACT);
  interaction.setPicker(pickerOpen);
  if (pickerOpen && overlay) overlay.focus();
});

ipcMain.on('settings:open', () => openSettings());

/* ---------------- Einstellungen ---------------- */
function openSettings() {
  if (settingsWin && !settingsWin.isDestroyed()) { settingsWin.focus(); return; }
  settingsWin = new BrowserWindow({
    width: 520, height: 680, resizable: false, minimizable: false, maximizable: false,
    title: 'Zeit-Overlay · Einstellungen', autoHideMenuBar: true, backgroundColor: '#ffffff',
    icon: path.join(__dirname, '..', 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, sandbox: true, nodeIntegration: false,
    },
  });
  settingsWin.loadFile(path.join(__dirname, 'renderer', 'settings.html'));
}

function tempProvider(form) {
  return createProvider({
    provider: form.provider || cfg.provider,
    token: form.token || cfg.token,
    teamId: form.teamId || cfg.teamId,
    spaceIds: [],
  });
}

ipcMain.handle('settings:get', () => config.publicView(cfg));
ipcMain.handle('settings:teams', (_e, form) => tempProvider(form).listTeams());
ipcMain.handle('settings:spaces', (_e, form) => tempProvider(form).listSpaces());
ipcMain.handle('settings:test', (_e, form) => tempProvider(form).testConnection());
ipcMain.handle('settings:save', (_e, form) => {
  const next = Object.assign({}, cfg, form);
  if (!form.token) next.token = cfg.token;          // leeres Feld = Token behalten
  if (form.clearToken) next.token = '';
  delete next.clearToken;
  next.idleOpacity = Math.min(1, Math.max(0.1, Number(next.idleOpacity) || 0.3));
  cfg = next;
  config.save(cfg);
  applyConfig();
  return config.publicView(cfg);
});

/* ---------------- Tray ---------------- */
function updateTray() {
  if (!tray) return;
  tray.setToolTip('Zeit-Overlay' + (current ? ' · läuft: ' + current.projectName : ''));
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: interaction.pinned ? 'Overlay lösen' : 'Overlay anheften (anklickbar)', click: () => interaction.togglePin() },
    { label: 'Einstellungen …', click: openSettings },
    {
      label: 'Position zurücksetzen',
      click: () => { const b = defaultBounds(); overlay.setBounds(b); cfg.bounds = { x: b.x, y: b.y }; config.save(cfg); },
    },
    { type: 'separator' },
    { label: 'Beenden', click: () => app.quit() },
  ]));
}

function createTray() {
  const img = nativeImage.createFromPath(path.join(__dirname, '..', 'build', 'icon.png')).resize({ width: 16, height: 16 });
  tray = new Tray(img);
  tray.on('click', () => interaction.togglePin());
  updateTray();
}

/* ---------------- Start ---------------- */
app.whenReady().then(() => {
  app.setAppUserModelId('de.czernitzki.zeit-overlay');
  cfg = config.load();
  provider = createProvider(cfg);
  createOverlay();
  createTray();
  registerShortcut();
  startHook();
  refreshCurrent();
  setInterval(refreshCurrent, POLL_MS);
  if (cfg.provider === 'clickup' && (!cfg.token || !cfg.teamId)) openSettings();
});

app.on('second-instance', () => openSettings());
app.on('window-all-closed', e => e.preventDefault());
app.on('will-quit', () => { globalShortcut.unregisterAll(); stopHook(); });

module.exports = { interaction };
