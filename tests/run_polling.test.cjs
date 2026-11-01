const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../webui/static/webui/run.js'), 'utf8');

function setup(fetchResult) {
  const timers = [];
  const cleared = [];
  let updates = 0;
  const elements = {
    'run-live': { dataset: { active: 'true', state: 'Running', elapsed: '1', statusUrl: '/api/runs/test/status' },
                  querySelector: () => ({ className: '' }) },
    'state-text': {}, 'state-glyph': {}, elapsed: {}, 'refresh-note': { hidden: true }
  };
  vm.runInNewContext(source, {
    document: { getElementById: id => elements[id] }, fetch: fetchResult,
    setInterval: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    clearInterval: id => cleared.push(id),
    window: { modelEvaluatorRefresh: () => { updates++; } }
  });
  return { timers, cleared, elements, updates: () => updates };
}

test('completed run stops timers and hands refresh to the focus-safe helper once', async () => {
  const state = setup(async () => ({ ok: true, json: async () => ({ state: 'Completed' }) }));
  await state.timers.find(t => t.ms === 3000).fn();
  assert.deepEqual(state.cleared, [1, 2]);
  assert.equal(state.updates(), 1);
});

test('two already pending terminal responses do not request two refreshes', async () => {
  const pending = [];
  const state = setup(() => new Promise(resolve => pending.push(resolve)));
  const poll = state.timers.find(t => t.ms === 3000).fn;
  const first = poll();
  const second = poll();
  pending.forEach(resolve => resolve({ ok: true, json: async () => ({ state: 'Failed' }) }));
  await Promise.all([first, second]);
  assert.equal(state.updates(), 1);
});

test('a stale request failure does not announce an error after completion', async () => {
  const pending = [];
  const state = setup(() => new Promise((resolve, reject) => pending.push({ resolve, reject })));
  const poll = state.timers.find(t => t.ms === 3000).fn;
  const first = poll();
  const second = poll();
  pending[0].resolve({ ok: true, json: async () => ({ state: 'Completed' }) });
  await first;
  pending[1].reject(new Error('late network failure'));
  await second;
  assert.equal(state.elements['refresh-note'].hidden, true);
  assert.equal(state.updates(), 1);
});
