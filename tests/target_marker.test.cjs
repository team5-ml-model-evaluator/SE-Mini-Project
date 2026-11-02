const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../webui/static/webui/app.js'), 'utf8');

function setup(selected) {
  const ready = [];
  const listeners = {};
  const select = { value: selected, addEventListener: (type, fn) => { listeners[type] = fn; } };
  const rows = ['age', 'city', 'bought'].map(name => ({
    dataset: { column: name },
    note: { hidden: true },
    control: { hidden: false },
    querySelector(selector) { return selector === '[data-target-note]' ? this.note : this.control; }
  }));
  const document = {
    getElementById: id => (id === 'id_target' ? select : null),
    querySelectorAll: selector => (selector === 'tr[data-column]' ? rows : []),
    addEventListener: (type, fn) => { if (type === 'DOMContentLoaded') ready.push(fn); }
  };
  vm.runInNewContext(source, { document, window: {} });
  ready.forEach(fn => fn());
  return { select, rows, change: () => listeners.change() };
}

test('the chosen target row shows a text note and hides its feature switch', () => {
  const state = setup('bought');
  assert.deepEqual(state.rows.map(r => r.note.hidden), [true, true, false]);
  assert.deepEqual(state.rows.map(r => r.control.hidden), [false, false, true]);
});

test('changing the target moves the note to the new row', () => {
  const state = setup('bought');
  state.select.value = 'age';
  state.change();
  assert.deepEqual(state.rows.map(r => r.note.hidden), [false, true, true]);
  assert.deepEqual(state.rows.map(r => r.control.hidden), [true, false, false]);
});

test('no target chosen leaves every row as a normal feature choice', () => {
  const state = setup('');
  assert.deepEqual(state.rows.map(r => r.note.hidden), [true, true, true]);
  assert.deepEqual(state.rows.map(r => r.control.hidden), [false, false, false]);
});
