'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { ClickUpProvider } = require('../src/providers/clickup');

/** Nachgebaute ClickUp-API: Routen → Antworten, protokolliert alle Aufrufe. */
function fakeFetch(routes) {
  const calls = [];
  const fn = async (url, opts) => {
    const path = url.replace('https://api.clickup.com/api/v2', '');
    const key = opts.method + ' ' + path;
    calls.push({ key, headers: opts.headers, body: opts.body ? JSON.parse(opts.body) : null });
    const hit = routes[key];
    if (hit === undefined) return { ok: false, status: 404, statusText: 'Not Found', text: async () => '{"err":"Route fehlt: ' + key + '"}' };
    const val = typeof hit === 'function' ? hit() : hit;
    if (val && val.__status) return { ok: false, status: val.__status, statusText: 'x', text: async () => JSON.stringify(val.body || {}) };
    return { ok: true, status: 200, text: async () => JSON.stringify(val) };
  };
  fn.calls = calls;
  return fn;
}

const ROUTES = {
  'GET /team': { teams: [{ id: 9001, name: 'Czernitzki' }] },
  'GET /team/9001/space?archived=false': { spaces: [{ id: 's1', name: 'Projekte' }, { id: 's2', name: 'Intern' }] },
  'GET /space/s1/folder?archived=false': { folders: [{ id: 'f1', name: 'Neubau', lists: [{ id: 'l1', name: '2026-041 Ahrens' }, { id: 'lx', name: 'Alt', archived: true }] }] },
  'GET /space/s1/list?archived=false': { lists: [{ id: 'l0', name: 'Sammelprojekt' }] },
  'GET /space/s2/folder?archived=false': { folders: [] },
  'GET /space/s2/list?archived=false': { lists: [{ id: 'l9', name: 'Büro' }] },
  'GET /list/l1/task?archived=false&include_closed=false&subtasks=true&page=0': {
    tasks: [{ id: 't1', name: 'GEG-Nachweis', status: { status: 'in arbeit' } }, { id: 't2', name: 'KfW-Antrag', status: { status: 'offen' } }],
    last_page: true,
  },
};

test('Projekte = Listen, gruppiert nach Space und Ordner, Archiv ausgeblendet', async () => {
  const f = fakeFetch(ROUTES);
  const p = new ClickUpProvider({ token: 'pk_x', teamId: '9001', fetchImpl: f });
  const items = await p.listProjects();
  assert.deepEqual(items.map(i => i.id).sort(), ['l0', 'l1', 'l9']);
  assert.equal(items.find(i => i.id === 'l1').group, 'Projekte / Neubau');
  assert.equal(f.calls[0].headers.Authorization, 'pk_x');
});

test('Space-Filter begrenzt die Projekte', async () => {
  const p = new ClickUpProvider({ token: 'pk_x', teamId: '9001', spaceIds: ['s2'], fetchImpl: fakeFetch(ROUTES) });
  const items = await p.listProjects();
  assert.deepEqual(items.map(i => i.id), ['l9']);
});

test('Aktivitäten = offene Aufgaben der Liste', async () => {
  const p = new ClickUpProvider({ token: 'pk_x', teamId: '9001', fetchImpl: fakeFetch(ROUTES) });
  const acts = await p.listActivities('l1');
  assert.deepEqual(acts.map(a => a.name), ['GEG-Nachweis', 'KfW-Antrag']);
});

test('Start beendet einen laufenden Timer zuerst und bucht auf die Aufgabe', async () => {
  let running = { id: 'e0', task: { id: 't9', name: 'Vorher' }, start: '1700000000000', task_location: { list_id: 'l9' } };
  const routes = Object.assign({}, ROUTES, {
    'GET /team/9001/time_entries/current': () => ({ data: running }),
    'POST /team/9001/time_entries/stop': () => { running = null; return { data: {} }; },
    'POST /team/9001/time_entries/start': () => {
      running = { id: 'e1', task: { id: 't1', name: 'GEG-Nachweis' }, start: '1700000600000', description: 'Abstimmung', task_location: { list_id: 'l1' } };
      return { data: running };
    },
  });
  const f = fakeFetch(routes);
  const p = new ClickUpProvider({ token: 'pk_x', teamId: '9001', fetchImpl: f });
  await p.listProjects();
  const cur = await p.start({ projectId: 'l1', activityId: 't1', note: 'Abstimmung' });
  const keys = f.calls.map(c => c.key).filter(k => k.includes('time_entries'));
  assert.deepEqual(keys, [
    'GET /team/9001/time_entries/current',
    'POST /team/9001/time_entries/stop',
    'POST /team/9001/time_entries/start',
    'GET /team/9001/time_entries/current',
  ]);
  assert.deepEqual(f.calls.find(c => c.key.endsWith('/start')).body, { tid: 't1', description: 'Abstimmung', billable: true });
  assert.equal(cur.projectName, '2026-041 Ahrens');
  assert.equal(cur.activityName, 'GEG-Nachweis');
  assert.equal(cur.start, 1700000600000);
});

test('Laufender Timer ohne Listenangabe holt die Liste über die Aufgabe', async () => {
  const routes = Object.assign({}, ROUTES, {
    'GET /team/9001/time_entries/current': { data: { id: 'e2', task: { id: 't7', name: 'Baustelle' }, start: '1700000000000' } },
    'GET /task/t7': { id: 't7', list: { id: 'l5', name: '2026-017 Schobüll' } },
  });
  const p = new ClickUpProvider({ token: 'pk_x', teamId: '9001', fetchImpl: fakeFetch(routes) });
  const cur = await p.getCurrent();
  assert.equal(cur.projectId, 'l5');
  assert.equal(cur.projectName, '2026-017 Schobüll');
});

test('Kein laufender Timer liefert null', async () => {
  const routes = Object.assign({}, ROUTES, { 'GET /team/9001/time_entries/current': { data: null } });
  const p = new ClickUpProvider({ token: 'pk_x', teamId: '9001', fetchImpl: fakeFetch(routes) });
  assert.equal(await p.getCurrent(), null);
});

test('Verständliche Fehler bei fehlendem oder falschem Token', async () => {
  await assert.rejects(new ClickUpProvider({ teamId: '9001' }).listTeams(), /Kein ClickUp-Token/);
  const p = new ClickUpProvider({ token: 'bad', fetchImpl: fakeFetch({ 'GET /team': { __status: 401, body: { err: 'Token invalid' } } }) });
  await assert.rejects(p.listTeams(), /401/);
});
