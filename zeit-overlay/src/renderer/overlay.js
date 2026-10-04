'use strict';
/* Overlay-Oberfläche. Spricht nur über window.zeit (preload.js) mit dem Hauptprozess. */
const $ = id => document.getElementById(id);
const api = window.zeit;

const S = {
  current: null,
  config: null,
  provider: '',
  active: false,
  pinned: false,
  panel: false,
  step: 'projects',        // 'projects' | 'activities'
  projects: [],
  activities: [],
  project: null,
  busy: false,
};

/* ---------------- Formate ---------------- */
const pad = n => String(n).padStart(2, '0');
function clock(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return pad(Math.floor(s / 3600)) + ':' + pad(Math.floor(s / 60) % 60) + ':' + pad(s % 60);
}
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
let msgTimer;
function message(text, ms = 6000) {
  const m = $('msg');
  m.textContent = text;
  m.hidden = !text;
  clearTimeout(msgTimer);
  if (text) msgTimer = setTimeout(() => { m.hidden = true; }, ms);
}

/* ---------------- Leiste ---------------- */
function renderBar() {
  const c = S.current;
  const root = $('root');
  root.classList.toggle('active', S.active);
  root.classList.toggle('running', !!c);
  root.classList.toggle('idle', !c);
  if (S.config) root.style.setProperty('--idle', String(S.config.idleOpacity));

  const hint = S.pinned ? 'angeheftet · ' + (S.config ? S.config.toggleShortcut.replace('Control', 'Strg') : '') + ' löst'
    : 'Strg halten zum Klicken';
  if (c) {
    $('proj').textContent = c.projectName || 'Projekt';
    $('act').textContent = (c.activityName || '') + (c.note ? ' · ' + c.note : '');
    $('proj').title = c.projectName || '';
    $('act').title = $('act').textContent;
  } else {
    const last = S.config && S.config.recent && S.config.recent[0];
    $('proj').textContent = 'Kein Timer aktiv';
    $('act').textContent = S.active && last ? 'Start setzt fort: ' + last.projectName : hint;
    $('proj').title = '';
    $('act').title = '';
  }
  const t = $('toggle');
  t.className = 'btn ' + (c ? 'stop' : 'go');
  t.title = c ? 'Timer stoppen und buchen' : 'Timer starten';
  t.setAttribute('aria-label', t.title);
  $('toggleIco').setAttribute('d', c ? 'M7 7h10v10H7z' : 'M8 5v14l11-7z');
  t.disabled = S.busy;
  $('pick').setAttribute('aria-expanded', String(S.panel));
  tick();
}

function tick() {
  $('time').textContent = S.current ? clock(Date.now() - S.current.start) : '00:00:00';
}
setInterval(tick, 1000);

/* ---------------- Auswahl ---------------- */
function openPanel(open) {
  S.panel = open;
  $('panel').hidden = !open;
  api.setPicker(open);
  if (open) {
    S.step = 'projects';
    S.project = null;
    $('search').value = '';
    $('note').value = '';
    loadProjects(false);
    setTimeout(() => $('search').focus(), 30);
  }
  renderBar();
}

async function loadProjects(refresh) {
  renderList(true);
  try {
    S.projects = await api.projects({ refresh });
  } catch (err) {
    S.projects = [];
    message(err.message);
  }
  renderList();
}

async function chooseProject(p) {
  S.project = p;
  S.step = 'activities';
  $('search').value = '';
  renderList(true);
  try {
    S.activities = await api.activities(p.id, {});
  } catch (err) {
    S.activities = [];
    message(err.message);
  }
  renderList();
  $('search').focus();
}

function matches(q, ...fields) {
  if (!q) return true;
  const hay = fields.join(' ').toLowerCase();
  return q.toLowerCase().split(/\s+/).every(w => hay.includes(w));
}

function renderList(loading) {
  const list = $('list');
  const q = $('search').value.trim();
  const projects = S.step === 'projects';
  $('back').hidden = projects;
  $('noteRow').hidden = projects;
  $('search').placeholder = projects ? 'Projekt suchen …' : 'Aktivität suchen in ' + (S.project ? S.project.name : '') + ' …';
  $('src').textContent = S.provider;
  if (loading) { list.innerHTML = '<div class="empty">Wird geladen …</div>'; return; }

  let h = '';
  const curP = S.current && S.current.projectId;
  const curA = S.current && S.current.activityId;
  if (projects) {
    const recent = ((S.config && S.config.recent) || []).filter(r => matches(q, r.projectName, r.activityName));
    if (recent.length) {
      h += '<div class="sect">Zuletzt</div>';
      recent.forEach((r, i) => {
        h += '<button class="item' + (r.projectId === curP && r.activityId === curA ? ' on' : '') + '" data-recent="' + i + '">'
          + '<span class="n">' + esc(r.projectName) + '</span><span class="s">' + esc(r.activityName) + '</span></button>';
      });
    }
    const groups = new Map();
    S.projects.filter(p => matches(q, p.name, p.group)).forEach(p => {
      if (!groups.has(p.group)) groups.set(p.group, []);
      groups.get(p.group).push(p);
    });
    groups.forEach((items, g) => {
      h += '<div class="sect">' + esc(g || 'Projekte') + '</div>';
      items.forEach(p => {
        h += '<button class="item' + (p.id === curP ? ' on' : '') + '" data-project="' + esc(p.id) + '"><span class="n">' + esc(p.name) + '</span></button>';
      });
    });
    if (!h) h = '<div class="empty">' + (q ? 'Kein Projekt passt zu „' + esc(q) + '“.' : 'Keine Projekte gefunden.') + '</div>';
  } else {
    const items = S.activities.filter(a => matches(q, a.name, a.status || ''));
    h += '<div class="sect">Aktivität wählen und starten</div>';
    items.forEach(a => {
      h += '<button class="item' + (a.id === curA ? ' on' : '') + '" data-activity="' + esc(a.id) + '"><span class="n">' + esc(a.name) + '</span>'
        + (a.status ? '<span class="s">' + esc(a.status) + '</span>' : '') + '</button>';
    });
    if (!items.length) h += '<div class="empty">' + (q ? 'Keine Aktivität passt.' : 'In diesem Projekt gibt es keine offenen Aktivitäten.') + '</div>';
  }
  list.innerHTML = h;
}

async function startWith(sel) {
  if (S.busy) return;
  S.busy = true; renderBar();
  try {
    S.current = await api.start(sel);
    const st = await api.state();
    S.config = st.config;
    openPanel(false);
    message('Timer läuft · ' + sel.projectName, 2500);
  } catch (err) {
    message(err.message);
  } finally {
    S.busy = false; renderBar();
  }
}

/* ---------------- Ereignisse ---------------- */
$('list').addEventListener('click', e => {
  const b = e.target.closest('button.item');
  if (!b) return;
  if (b.dataset.recent != null) {
    const r = S.config.recent[+b.dataset.recent];
    startWith({ ...r, note: '' });
  } else if (b.dataset.project) {
    const p = S.projects.find(x => x.id === b.dataset.project);
    if (p) chooseProject(p);
  } else if (b.dataset.activity) {
    const a = S.activities.find(x => x.id === b.dataset.activity);
    if (a && S.project) {
      startWith({
        projectId: S.project.id, projectName: S.project.name,
        activityId: a.id, activityName: a.name, note: $('note').value.trim(),
      });
    }
  }
});

$('search').addEventListener('input', () => renderList());
$('search').addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const first = $('list').querySelector('button.item');
    if (first) first.click();
  } else if (e.key === 'Escape') {
    if (S.step === 'activities') $('back').click(); else openPanel(false);
  }
});
$('note').addEventListener('keydown', e => { if (e.key === 'Escape') openPanel(false); });
$('back').addEventListener('click', () => { S.step = 'projects'; $('search').value = ''; renderList(); $('search').focus(); });
$('reload').addEventListener('click', () => (S.step === 'projects' ? loadProjects(true)
  : api.activities(S.project.id, { refresh: true }).then(a => { S.activities = a; renderList(); }, err => message(err.message))));
$('settings').addEventListener('click', () => { openPanel(false); api.openSettings(); });
$('pick').addEventListener('click', () => openPanel(!S.panel));

$('toggle').addEventListener('click', async () => {
  if (S.busy) return;
  if (S.current) {
    S.busy = true; renderBar();
    try {
      const dauer = clock(Date.now() - S.current.start);
      await api.stop();
      S.current = null;
      message('Gebucht · ' + dauer, 3000);
    } catch (err) {
      message(err.message);
    } finally {
      S.busy = false; renderBar();
    }
    return;
  }
  const last = S.config && S.config.recent && S.config.recent[0];
  if (last) startWith({ ...last, note: '' });
  else openPanel(true);
});

// Klick außerhalb (Fenster verliert den Fokus) schließt die Auswahl.
window.addEventListener('blur', () => { if (S.panel) openPanel(false); });

api.onInteractive(v => { S.active = v.on; S.pinned = v.pinned; renderBar(); });
api.onCurrent(c => { S.current = c; renderBar(); if (S.panel) renderList(); });
api.onConfig(c => {
  S.config = c;
  api.state().then(st => { S.provider = st.provider; S.current = st.current; renderBar(); });
  renderBar();
});
api.onError(m => message(m));

api.state().then(st => {
  S.current = st.current;
  S.config = st.config;
  S.provider = st.provider;
  S.active = st.interactive;
  S.pinned = st.pinned;
  renderBar();
});
