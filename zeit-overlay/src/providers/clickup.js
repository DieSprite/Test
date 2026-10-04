'use strict';
/*
 * ClickUp-Anbindung über die REST-API v2.
 *
 * Zuordnung:
 *   Projekt   = ClickUp-Liste   (gruppiert nach Space / Ordner)
 *   Aktivität = Aufgabe in dieser Liste
 * ClickUp bucht Zeit immer auf eine Aufgabe, deshalb ist die Aktivität Pflicht.
 */
const BASE = 'https://api.clickup.com/api/v2';
const CACHE_MS = 10 * 60 * 1000;

class ClickUpProvider {
  constructor({ token, teamId, spaceIds, fetchImpl } = {}) {
    this.token = token;
    this.teamId = teamId;
    this.spaceIds = Array.isArray(spaceIds) ? spaceIds : [];
    this.fetch = fetchImpl || globalThis.fetch;
    this.projectCache = null;
    this.taskList = new Map();   // Aufgaben-ID → { listId, listName }
    this.activityCache = new Map();
  }

  get label() { return 'ClickUp'; }

  async _req(method, path, body) {
    if (!this.token) throw new Error('Kein ClickUp-Token hinterlegt. Bitte in den Einstellungen eintragen.');
    const res = await this.fetch(BASE + path, {
      method,
      headers: { Authorization: this.token, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { /* kein JSON */ }
    if (!res.ok) {
      const msg = (data && (data.err || data.error)) || text || res.statusText;
      if (res.status === 401) throw new Error('ClickUp lehnt das Token ab (401). Bitte Token prüfen.');
      if (res.status === 429) throw new Error('ClickUp-Anfragelimit erreicht. Bitte kurz warten.');
      throw new Error('ClickUp ' + res.status + ': ' + msg);
    }
    return data;
  }

  _needTeam() {
    if (!this.teamId) throw new Error('Kein ClickUp-Workspace gewählt. Bitte in den Einstellungen auswählen.');
  }

  async listTeams() {
    const d = await this._req('GET', '/team');
    return (d.teams || []).map(t => ({ id: String(t.id), name: t.name }));
  }

  async listSpaces() {
    this._needTeam();
    const d = await this._req('GET', `/team/${this.teamId}/space?archived=false`);
    return (d.spaces || []).map(s => ({ id: String(s.id), name: s.name }));
  }

  async testConnection() {
    const teams = await this.listTeams();
    return { ok: true, info: teams.length + ' Workspace(s) erreichbar' };
  }

  async listProjects({ refresh } = {}) {
    if (!refresh && this.projectCache && Date.now() - this.projectCache.at < CACHE_MS) {
      return this.projectCache.items;
    }
    let spaces = await this.listSpaces();
    if (this.spaceIds.length) spaces = spaces.filter(s => this.spaceIds.includes(s.id));
    const items = [];
    for (const s of spaces) {
      const [f, l] = await Promise.all([
        this._req('GET', `/space/${s.id}/folder?archived=false`),
        this._req('GET', `/space/${s.id}/list?archived=false`),
      ]);
      for (const list of l.lists || []) {
        items.push({ id: String(list.id), name: list.name, group: s.name });
      }
      for (const folder of f.folders || []) {
        for (const list of folder.lists || []) {
          if (list.archived) continue;
          items.push({ id: String(list.id), name: list.name, group: s.name + ' / ' + folder.name });
        }
      }
    }
    this.projectCache = { at: Date.now(), items };
    return items;
  }

  async listActivities(projectId, { refresh } = {}) {
    const hit = this.activityCache.get(projectId);
    if (!refresh && hit && Date.now() - hit.at < CACHE_MS) return hit.items;
    const items = [];
    for (let page = 0; page < 20; page++) {
      const d = await this._req('GET',
        `/list/${projectId}/task?archived=false&include_closed=false&subtasks=true&page=${page}`);
      const tasks = d.tasks || [];
      for (const t of tasks) {
        items.push({ id: String(t.id), name: t.name, status: t.status && t.status.status });
      }
      if (d.last_page === true || tasks.length < 100) break;
    }
    const proj = (this.projectCache && this.projectCache.items.find(p => p.id === projectId)) || null;
    for (const a of items) this.taskList.set(a.id, { listId: projectId, listName: proj ? proj.name : '' });
    this.activityCache.set(projectId, { at: Date.now(), items });
    return items;
  }

  async _listOfTask(task) {
    const known = this.taskList.get(String(task.id));
    if (known) return known;
    const t = await this._req('GET', `/task/${task.id}`);
    const info = { listId: t.list ? String(t.list.id) : '', listName: t.list ? t.list.name : '' };
    this.taskList.set(String(task.id), info);
    return info;
  }

  async getCurrent() {
    this._needTeam();
    const d = await this._req('GET', `/team/${this.teamId}/time_entries/current`);
    const e = d && d.data;
    if (!e || !e.start) return null;
    let project = { listId: '', listName: '' };
    if (e.task && e.task.id) {
      if (e.task_location && e.task_location.list_id) {
        const p = this.projectCache && this.projectCache.items.find(x => x.id === String(e.task_location.list_id));
        project = { listId: String(e.task_location.list_id), listName: p ? p.name : '' };
        if (!project.listName) project = await this._listOfTask(e.task);
      } else {
        project = await this._listOfTask(e.task);
      }
    }
    return {
      id: String(e.id),
      projectId: project.listId,
      projectName: project.listName || 'ohne Liste',
      activityId: e.task ? String(e.task.id) : '',
      activityName: e.task ? e.task.name : 'ohne Aufgabe',
      note: e.description || '',
      start: Number(e.start),
    };
  }

  async start({ projectId, activityId, note }) {
    this._needTeam();
    if (!activityId) throw new Error('Bitte eine Aktivität (Aufgabe) wählen.');
    // Einen laufenden Timer zuerst sauber beenden, damit nichts doppelt läuft.
    const cur = await this.getCurrent();
    if (cur) await this.stop();
    await this._req('POST', `/team/${this.teamId}/time_entries/start`, {
      tid: activityId,
      description: note || '',
      billable: true,
    });
    if (projectId) {
      const p = this.projectCache && this.projectCache.items.find(x => x.id === projectId);
      this.taskList.set(String(activityId), { listId: projectId, listName: p ? p.name : '' });
    }
    return this.getCurrent();
  }

  async stop() {
    this._needTeam();
    await this._req('POST', `/team/${this.teamId}/time_entries/stop`);
    return null;
  }
}

module.exports = { ClickUpProvider };
