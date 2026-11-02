const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../webui/static/webui/batch.js'), 'utf8');

function setup(fetchResult) {
  const timers = [];
  const elements = {
    'batch-live': { dataset: { version: 'same', statusUrl: '/api/evaluations/test/status' } },
    'batch-refresh-note': { hidden: true },
    'elapsed-r-test': { textContent: '' }
  };
  let reloads = 0;
  vm.runInNewContext(source, {
    document: { getElementById: id => elements[id] }, AbortController,
    fetch: fetchResult,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    clearTimeout: () => {},
    window: { modelEvaluatorRefresh: () => { reloads++; } }
  });
  return { timers, elements, reloads: () => reloads };
}

test('unchanged status updates text and schedules the next poll after completion', async () => {
  const state = setup(async () => ({ ok: true, json: async () => ({
    version: 'same', active: true, jobs: [{ key: 'r-test', elapsed_s: 3.5 }]
  }) }));
  await state.timers[0].fn();
  assert.equal(state.elements['elapsed-r-test'].textContent, '3.5');
  assert.equal(state.reloads(), 0);
  assert.equal(state.timers.filter(timer => timer.ms === 3000).length, 2);
});

test('state change reloads once and stops polling', async () => {
  const state = setup(async () => ({ ok: true, json: async () => ({ version: 'changed', active: false }) }));
  await state.timers[0].fn();
  assert.equal(state.reloads(), 1);
  assert.equal(state.timers.filter(timer => timer.ms === 3000).length, 1);
});

test('network errors show last-known-status guidance and retry', async () => {
  const state = setup(async () => { throw new Error('offline'); });
  await state.timers[0].fn();
  assert.equal(state.elements['batch-refresh-note'].hidden, false);
  assert.equal(state.timers.filter(timer => timer.ms === 3000).length, 2);
});

test('a pending request does not overlap with another poll', async () => {
  let resolve;
  const state = setup(() => new Promise(done => { resolve = done; }));
  const pending = state.timers[0].fn();
  assert.equal(state.timers.filter(timer => timer.ms === 3000).length, 1);
  resolve({ ok: true, json: async () => ({ version: 'same', active: true, jobs: [] }) });
  await pending;
  assert.equal(state.timers.filter(timer => timer.ms === 3000).length, 2);
});

test('request timeout aborts the request and allows a later retry', async () => {
  const state = setup((url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('timeout')));
  }));
  const pending = state.timers[0].fn();
  state.timers.find(timer => timer.ms === 5000).fn();
  await pending;
  assert.equal(state.elements['batch-refresh-note'].hidden, false);
  assert.equal(state.timers.filter(timer => timer.ms === 3000).length, 2);
});
