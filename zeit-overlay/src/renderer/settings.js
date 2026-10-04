'use strict';
const $ = id => document.getElementById(id);
const api = window.zeit.settings;
let cfg = null;

function status(text, err) {
  $('status').textContent = text || '';
  $('status').className = err ? 'err' : '';
}
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function form() {
  return { provider: $('provider').value, token: $('token').value.trim(), teamId: $('teamId').value };
}
function showProvider() {
  $('cuBox').hidden = $('provider').value !== 'clickup';
}
function showOpacity() {
  const v = Number($('idleOpacity').value);
  $('opVal').textContent = Math.round(v * 100) + ' % sichtbar, ' + Math.round((1 - v) * 100) + ' % durchsichtig';
}

async function loadTeams() {
  status('Workspaces werden geladen …');
  try {
    const teams = await api.teams(form());
    const keep = $('teamId').value || cfg.teamId;
    $('teamId').innerHTML = '<option value="">– bitte wählen –</option>'
      + teams.map(t => '<option value="' + esc(t.id) + '"' + (t.id === keep ? ' selected' : '') + '>' + esc(t.name) + '</option>').join('');
    if (teams.length === 1) $('teamId').value = teams[0].id;
    status(teams.length + ' Workspace(s) gefunden');
    if ($('teamId').value) loadSpaces();
  } catch (err) {
    status(err.message, true);
  }
}

async function loadSpaces() {
  if (!$('teamId').value) { $('spaces').innerHTML = '<small>Workspace wählen, dann erscheinen die Spaces.</small>'; return; }
  try {
    const spaces = await api.spaces(form());
    const sel = new Set(cfg.teamId === $('teamId').value ? cfg.spaceIds || [] : []);
    $('spaces').innerHTML = spaces.map(s => '<label><input type="checkbox" value="' + esc(s.id) + '"'
      + (sel.has(s.id) ? ' checked' : '') + '><span>' + esc(s.name) + '</span></label>').join('')
      || '<small>Keine Spaces gefunden.</small>';
  } catch (err) {
    status(err.message, true);
  }
}

$('provider').addEventListener('change', showProvider);
$('idleOpacity').addEventListener('input', showOpacity);
$('loadTeams').addEventListener('click', loadTeams);
$('teamId').addEventListener('change', loadSpaces);
$('test').addEventListener('click', async () => {
  status('Verbindung wird geprüft …');
  try { const r = await api.test(form()); status('Verbindung steht · ' + r.info); }
  catch (err) { status(err.message, true); }
});

$('f').addEventListener('submit', async e => {
  e.preventDefault();
  const f = form();
  if (f.provider === 'clickup' && !f.token && !cfg.hasToken) { status('Bitte ein ClickUp-Token eintragen.', true); return; }
  if (f.provider === 'clickup' && !f.teamId) { status('Bitte einen Workspace wählen.', true); return; }
  try {
    cfg = await api.save({
      ...f,
      spaceIds: [...document.querySelectorAll('#spaces input:checked')].map(i => i.value),
      idleOpacity: Number($('idleOpacity').value),
      ctrlHold: $('ctrlHold').checked,
      toggleShortcut: $('toggleShortcut').value.trim(),
      autostart: $('autostart').checked,
    });
    $('token').value = '';
    $('token').placeholder = cfg.hasToken ? 'gespeichert – leer lassen, um es zu behalten' : 'pk_…';
    status('Gespeichert');
  } catch (err) {
    status(err.message, true);
  }
});

api.get().then(c => {
  cfg = c;
  $('provider').value = c.provider;
  $('idleOpacity').value = c.idleOpacity;
  $('ctrlHold').checked = !!c.ctrlHold;
  $('toggleShortcut').value = c.toggleShortcut || '';
  $('autostart').checked = !!c.autostart;
  $('token').placeholder = c.hasToken ? 'gespeichert – leer lassen, um es zu behalten' : 'pk_…';
  if (c.teamId) $('teamId').innerHTML = '<option value="' + esc(c.teamId) + '" selected>gespeicherter Workspace</option>';
  showProvider();
  showOpacity();
  if (c.provider === 'clickup' && c.hasToken) loadTeams();
});
