'use strict';
/*
 * Demo-Anbieter ohne Verbindung nach außen – zum Ausprobieren des Overlays.
 * Der laufende Timer liegt nur im Speicher.
 */
const PROJECTS = [
  { id: 'p1', name: '2026-041 Ahrens, Husum', group: 'Neubau' },
  { id: 'p2', name: '2026-038 Deichbau Nord, Husum', group: 'Neubau' },
  { id: 'p3', name: '2026-029 Petersen, Bredstedt', group: 'Sanierung' },
  { id: 'p4', name: '2026-017 Wohnanlage Schobüll', group: 'Sanierung' },
  { id: 'p5', name: 'Büro allgemein', group: 'Intern' },
];
const ACTIVITIES = [
  { id: 'statik', name: 'Tragwerksplanung' },
  { id: 'bauphysik', name: 'Bauphysik / GEG-Nachweis' },
  { id: 'kfw', name: 'KfW-Antrag und Nachweise' },
  { id: 'wbn', name: 'Wärmebrückennachweis' },
  { id: 'baustelle', name: 'Baustellentermin' },
  { id: 'abstimmung', name: 'Abstimmung Bauherr' },
];

class DemoProvider {
  constructor() { this.current = null; }
  get label() { return 'Demo'; }
  async testConnection() { return { ok: true, info: 'Demo-Daten, keine Verbindung' }; }
  async listProjects() { return PROJECTS; }
  async listActivities() { return ACTIVITIES; }
  async getCurrent() { return this.current; }
  async start({ projectId, activityId, note }) {
    const p = PROJECTS.find(x => x.id === projectId);
    const a = ACTIVITIES.find(x => x.id === activityId);
    if (!p || !a) throw new Error('Projekt oder Aktivität unbekannt.');
    this.current = {
      id: 'demo-' + Date.now(), projectId, projectName: p.name,
      activityId, activityName: a.name, note: note || '', start: Date.now(),
    };
    return this.current;
  }
  async stop() { this.current = null; return null; }
}

module.exports = { DemoProvider };
