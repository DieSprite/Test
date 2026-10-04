'use strict';
/*
 * Einstellungen in %APPDATA%\Zeit-Overlay\config.json.
 * Das ClickUp-Token wird mit der Windows-Kontoverschlüsselung (DPAPI über safeStorage)
 * abgelegt und steht nie im Klartext in der Datei.
 */
const fs = require('fs');
const path = require('path');
const { app, safeStorage } = require('electron');

const DEFAULTS = {
  provider: 'demo',
  teamId: '',
  spaceIds: [],
  idleOpacity: 0.3,       // 70 % durchsichtig
  activeOpacity: 1,
  toggleShortcut: 'Control+Alt+T',
  ctrlHold: true,
  autostart: false,
  bounds: null,
  recent: [],             // zuletzt genutzte Projekt/Aktivität-Paare
};

function file() { return path.join(app.getPath('userData'), 'config.json'); }

function load() {
  let raw = {};
  try { raw = JSON.parse(fs.readFileSync(file(), 'utf8')); } catch { /* erster Start */ }
  const cfg = Object.assign({}, DEFAULTS, raw);
  cfg.token = '';
  if (raw.tokenEnc && safeStorage.isEncryptionAvailable()) {
    try { cfg.token = safeStorage.decryptString(Buffer.from(raw.tokenEnc, 'base64')); } catch { /* unlesbar */ }
  }
  delete cfg.tokenEnc;
  return cfg;
}

function save(cfg) {
  const out = Object.assign({}, cfg);
  delete out.token;
  if (cfg.token && safeStorage.isEncryptionAvailable()) {
    out.tokenEnc = safeStorage.encryptString(cfg.token).toString('base64');
  }
  fs.mkdirSync(path.dirname(file()), { recursive: true });
  fs.writeFileSync(file(), JSON.stringify(out, null, 2));
}

/** Öffentliche Sicht für die Oberfläche – ohne Token. */
function publicView(cfg) {
  const v = Object.assign({}, cfg);
  v.hasToken = !!cfg.token;
  delete v.token;
  return v;
}

module.exports = { load, save, publicView, DEFAULTS };
