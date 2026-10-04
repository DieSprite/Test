'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { Interaction } = require('../src/interaction');

function make() {
  const log = [];
  const i = new Interaction(v => log.push(v));
  return { i, log };
}

test('Strg halten macht anklickbar, Loslassen außerhalb nicht mehr', () => {
  const { i, log } = make();
  i.ctrlDown();
  assert.equal(i.interactive, true);
  i.ctrlUp(false);
  assert.equal(i.interactive, false);
  assert.deepEqual(log, [true, false]);
});

test('Strg+C zählt nicht als Overlay-Shortcut', () => {
  const { i } = make();
  i.ctrlDown();
  i.otherKey();
  assert.equal(i.interactive, false);
  i.ctrlUp(true);   // selbst über dem Overlay: es war ein normaler Shortcut
  assert.equal(i.interactive, false);
});

test('Loslassen über dem Overlay hält es offen, bis die Maus es verlässt', () => {
  const { i } = make();
  i.ctrlDown();
  i.ctrlUp(true);
  assert.equal(i.interactive, true);
  i.cursor(true);
  assert.equal(i.interactive, true);
  i.cursor(false);
  assert.equal(i.interactive, false);
});

test('Tastenwiederholung löst kein erneutes Ereignis aus', () => {
  const { i, log } = make();
  i.ctrlDown(); i.ctrlDown(); i.ctrlDown();
  assert.deepEqual(log, [true]);
});

test('Offene Auswahl bleibt anklickbar, auch wenn die Maus kurz rausgeht', () => {
  const { i } = make();
  i.ctrlDown(); i.ctrlUp(true);
  i.setPicker(true);
  i.cursor(false);
  assert.equal(i.interactive, true);
  i.setPicker(false);
  i.cursor(false);
  assert.equal(i.interactive, false);
});

test('Anheften hält dauerhaft, erneutes Drücken löst', () => {
  const { i } = make();
  assert.equal(i.togglePin(), true);
  i.cursor(false);
  assert.equal(i.interactive, true);
  assert.equal(i.togglePin(), false);
  assert.equal(i.interactive, false);
});
