'use strict';
/*
 * Anbieter-Auswahl. Jeder Anbieter liefert dieselben Methoden:
 *   listProjects() · listActivities(projectId) · getCurrent()
 *   start({ projectId, activityId, note }) · stop() · testConnection()
 * Ein späterer Projektbuch-Anbieter wird hier ergänzt, das Overlay bleibt gleich.
 */
const { ClickUpProvider } = require('./clickup');
const { DemoProvider } = require('./demo');

function createProvider(cfg) {
  switch (cfg.provider) {
    case 'clickup':
      return new ClickUpProvider({ token: cfg.token, teamId: cfg.teamId, spaceIds: cfg.spaceIds });
    case 'demo':
    default:
      return new DemoProvider();
  }
}

module.exports = { createProvider };
