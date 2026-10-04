'use strict';
const { contextBridge, ipcRenderer } = require('electron');

const on = (ch, fn) => {
  const h = (_e, v) => fn(v);
  ipcRenderer.on(ch, h);
  return () => ipcRenderer.removeListener(ch, h);
};

contextBridge.exposeInMainWorld('zeit', {
  // Overlay
  state: () => ipcRenderer.invoke('state:get'),
  projects: opts => ipcRenderer.invoke('projects:list', opts),
  activities: (id, opts) => ipcRenderer.invoke('activities:list', id, opts),
  start: sel => ipcRenderer.invoke('timer:start', sel),
  stop: () => ipcRenderer.invoke('timer:stop'),
  refresh: () => ipcRenderer.invoke('timer:refresh'),
  setPicker: open => ipcRenderer.send('picker:set', open),
  openSettings: () => ipcRenderer.send('settings:open'),
  onInteractive: fn => on('interactive', fn),
  onCurrent: fn => on('current', fn),
  onConfig: fn => on('config', fn),
  onError: fn => on('error', fn),
  // Einstellungen
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    teams: form => ipcRenderer.invoke('settings:teams', form),
    spaces: form => ipcRenderer.invoke('settings:spaces', form),
    test: form => ipcRenderer.invoke('settings:test', form),
    save: form => ipcRenderer.invoke('settings:save', form),
  },
});
