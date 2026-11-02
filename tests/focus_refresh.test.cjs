const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../webui/static/webui/app.js'), 'utf8');

function setup(focused) {
  const ready = [];
  let reloads = 0;
  let clicks = {};
  const body = {};
  const html = {};
  const note = { hidden: true };
  const button = { addEventListener: (type, fn) => { clicks[type] = fn; } };
  const document = {
    body, documentElement: html, activeElement: focused ? button : body,
    getElementById: id => ({ 'results-update': note, 'refresh-results': button }[id]),
    addEventListener: (type, fn) => { if (type === 'DOMContentLoaded') ready.push(fn); }
  };
  const window = { location: { reload: () => { reloads++; } } };
  vm.runInNewContext(source, { document, window });
  ready.forEach(fn => fn());
  return { document, window, button, note, clicks, reloads: () => reloads };
}

test('automatic result refresh does not discard the focused control', () => {
  const state = setup(true);
  state.window.modelEvaluatorRefresh();
  assert.equal(state.reloads(), 0);
  assert.equal(state.note.hidden, false);
  assert.equal(state.document.activeElement, state.button);
  state.clicks.click();
  assert.equal(state.reloads(), 1);
});

test('result refresh is automatic when no control has focus', () => {
  const state = setup(false);
  state.window.modelEvaluatorRefresh();
  assert.equal(state.reloads(), 1);
});
