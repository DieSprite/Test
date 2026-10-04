'use strict';
/*
 * Entwicklerhilfe: startet das Overlay im Demo-Modus und speichert Bildschirmfotos
 * der Zustände nach ./shots. Aufruf: npx electron scripts/shots.js
 */
const path = require('path');
const fs = require('fs');
const { app, BrowserWindow } = require('electron');

const dir = path.join(__dirname, '..', 'shots');
app.setPath('userData', path.join(dir, 'profil'));
fs.mkdirSync(dir, { recursive: true });
const { interaction } = require('../src/main');

const wait = ms => new Promise(r => setTimeout(r, ms));
async function shot(win, name) {
  await wait(400);
  const img = await win.webContents.capturePage();
  fs.writeFileSync(path.join(dir, name + '.png'), img.toPNG());
  console.log('Foto:', name);
}

app.whenReady().then(async () => {
  await wait(2500);
  const win = BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes('overlay.html'));
  const js = code => win.webContents.executeJavaScript(code);
  await shot(win, '1-ruhe');
  interaction.ctrlDown();
  await shot(win, '2-strg');
  await js("document.getElementById('pick').click()");
  await wait(600);
  await shot(win, '3-auswahl');
  await js("document.querySelector('[data-project=\"p1\"]').click()");
  await wait(400);
  await js("document.getElementById('note').value='Abstimmung Fenster'");
  await shot(win, '4-aktivitaet');
  await js("document.querySelector('[data-activity=\"bauphysik\"]').click()");
  await wait(3200);
  await shot(win, '5-laeuft-aktiv');
  interaction.ctrlUp(false);
  await shot(win, '6-laeuft-ruhe');
  const st = await js("({cls: document.getElementById('root').className, proj: document.getElementById('proj').textContent, time: document.getElementById('time').textContent})");
  console.log('Zustand:', JSON.stringify(st));
  app.exit(0);
});
