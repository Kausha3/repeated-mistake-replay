#!/usr/bin/env node
'use strict';

/*
 * Dependency-free state checks for the built browser page. Run with Node 18+:
 *   node test_web_state.cjs
 * Build docs/index.html before running this file.
 *
 * This deliberately small mock DOM exercises event order, rendered text and
 * download cleanup. It is not a browser, a security sandbox, a CSP enforcement
 * test, an accessibility assessment or a real download compatibility test.
 * Only this repository's trusted, built page script is evaluated in the VM.
 * Fault injection checks recovery, not the frequency of browser API failures.
 */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { Blob } = require('node:buffer');
const { TextEncoder, TextDecoder } = require('node:util');

const html = fs.readFileSync(path.join(__dirname, 'docs', 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 1, 'Expected one inline application script');
const script = scripts[0][1];

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function bytes(raw) {
  return Uint8Array.from(Buffer.from(raw, 'utf8')).buffer;
}

function runtime(faults = {}) {
  const elements = new Map();
  const created = [], revoked = [], timers = [], networkCalls = [];
  let sequence = 0;

  class Element {
    constructor(tag, id = '') {
      this.tag = tag;
      this.id = id;
      this.children = [];
      this.listeners = new Map();
      this.disabled = id === 'download';
      this.files = [];
      this._value = '';
      this._text = '';
    }
    set value(value) {
      this._value = String(value);
      if (this.id === 'file' && value === '') this.files = [];
    }
    get value() { return this._value; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() {
      return this._text + this.children.map(child => child.textContent).join('');
    }
    set innerHTML(value) { throw new Error('Unexpected innerHTML assignment'); }
    set selectedIndex(index) { this.value = this.children[index]?.value ?? ''; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this._text = ''; this.children = children; }
    addEventListener(type, callback) {
      if (!this.listeners.has(type)) this.listeners.set(type, []);
      this.listeners.get(type).push(callback);
    }
    dispatch(type) {
      return Promise.all((this.listeners.get(type) ?? []).map(fn => fn({ target: this })));
    }
    click() {
      if (this.disabled) return;
      if (this.tag === 'a' && faults.click) throw new Error('Injected download click failure');
      return this.dispatch('click');
    }
  }

  for (const id of ['input', 'error', 'result', 'download', 'file', 'examples', 'analyze', 'clear']) {
    elements.set(id, new Element(id === 'input' ? 'textarea' : id === 'examples' ? 'select' : 'button', id));
  }
  elements.get('examples').append(new Element('option'));
  const document = {
    getElementById: id => elements.get(id),
    createElement: tag => new Element(tag),
  };
  const blockedNetwork = kind => () => {
    networkCalls.push(kind);
    throw new Error('Unexpected network call in local inspection');
  };
  const context = vm.createContext({
    document, window: {}, Blob, TextEncoder, TextDecoder,
    URL: {
      createObjectURL(blob) {
        if (faults.url) throw new Error('Injected object URL failure');
        const url = 'blob:local-test/' + (++sequence);
        created.push({ url, blob });
        return url;
      },
      revokeObjectURL: url => revoked.push(url),
    },
    setTimeout(callback) { timers.push(callback); return timers.length; },
    fetch: blockedNetwork('fetch'),
    XMLHttpRequest: blockedNetwork('XMLHttpRequest'),
    WebSocket: blockedNetwork('WebSocket'),
  });
  vm.runInContext(script, context, { timeout: 1000 });
  const get = id => elements.get(id);
  const fixture = () => JSON.parse(JSON.stringify(context.window.REPLAY_DATA.cases[0]));
  assert(fixture().provenance === 'synthetic', 'Use only a bundled synthetic fixture');
  const report = () => {
    const find = node => node.tag === 'pre' ? node : node.children.map(find).find(Boolean);
    const pre = find(get('result'));
    return pre ? JSON.parse(pre.textContent) : null;
  };
  const edit = async record => {
    get('input').value = typeof record === 'string' ? record : JSON.stringify(record);
    await get('input').dispatch('input');
  };
  const file = (raw, options = {}) => ({
    name: options.name ?? 'synthetic-record.json',
    size: options.size ?? Buffer.byteLength(raw, 'utf8'),
    arrayBuffer: () => options.promise ?? Promise.resolve(bytes(raw)),
  });
  const choose = selected => {
    get('file').files = selected ? [selected] : [];
    get('file').value = selected ? 'selected:' + selected.name : '';
    return get('file').dispatch('change');
  };
  const flushTimers = () => { while (timers.length) timers.shift()(); };
  return { get, fixture, report, edit, file, choose, context, created, revoked, networkCalls, flushTimers,
    inspect: () => get('analyze').click() };
}

const tests = [];
const test = (name, run) => tests.push({ name, run });

test('download contains current input and releases its object URL', async () => {
  const x = runtime(), record = x.fixture();
  await x.edit(record); await x.inspect();
  assert.equal(x.get('download').disabled, false);
  await x.get('download').click();
  assert.equal(x.created.length, 1);
  const downloaded = JSON.parse(await x.created[0].blob.text());
  assert.deepEqual(downloaded.case, record);
  x.flushTimers();
  assert.deepEqual(x.revoked, [x.created[0].url]);
});

test('an edit and malformed paste invalidate the previous report', async () => {
  const x = runtime();
  await x.edit(x.fixture()); await x.inspect();
  await x.edit('{');
  assert.equal(x.report(), null);
  assert.equal(x.get('download').disabled, true);
  await x.inspect();
  assert(x.get('error').textContent.length > 0);
  assert.equal(x.report(), null);
});

for (const failure of ['oversized', 'invalid UTF-8', 'read rejection']) {
  test('failed file cannot revive an old record: ' + failure, async () => {
    const x = runtime(), old = x.fixture(); old.id = 'OLD_SYNTHETIC_RECORD';
    await x.edit(old); await x.inspect();
    let selected;
    if (failure === 'oversized') selected = x.file('', { size: 100001 });
    if (failure === 'invalid UTF-8') selected = x.file('', {
      size: 2, promise: Promise.resolve(Uint8Array.from([0xc3, 0x28]).buffer),
    });
    if (failure === 'read rejection') selected = x.file('', {
      size: 100, promise: Promise.reject(new Error('Injected file read failure')),
    });
    await x.choose(selected);
    assert.equal(x.get('input').value, '');
    assert.equal(x.get('file').value, '');
    assert(x.get('error').textContent.length > 0);
    assert.equal(x.get('analyze').disabled, false);
    assert.equal(x.report(), null);
    assert.equal(x.get('download').disabled, true);
    await x.inspect();
    assert.equal(x.report(), null);
    assert.equal(x.get('download').disabled, true);
  });
}

for (const source of ['{', JSON.stringify({ messages: [{ role: 'user', content: 'synthetic' }] })]) {
  test('malformed or raw vendor file stays invalid: ' + source.slice(0, 18), async () => {
    const x = runtime();
    await x.edit(x.fixture()); await x.inspect();
    await x.choose(x.file(source));
    assert.equal(x.get('input').value, source);
    assert(x.get('error').textContent.length > 0);
    assert.equal(x.report(), null);
    assert.equal(x.get('download').disabled, true);
  });
}

for (const cancel of ['clear', 'edit', 'example']) {
  test('cancel pending file through ' + cancel, async () => {
    const x = runtime(), pending = deferred(), record = x.fixture(); record.id = 'STALE_FILE';
    const read = x.choose(x.file('', { size: 500, promise: pending.promise }));
    assert.equal(x.get('input').value, '');
    assert.equal(x.get('analyze').disabled, true);
    await x.inspect(); assert.equal(x.report(), null);
    if (cancel === 'clear') await x.get('clear').click();
    if (cancel === 'edit') await x.edit('{');
    if (cancel === 'example') {
      x.get('examples').value = '0'; await x.get('examples').dispatch('change');
    }
    const current = x.get('input').value, currentReport = x.report();
    assert.equal(x.get('analyze').disabled, false);
    pending.resolve(bytes(JSON.stringify(record))); await read;
    assert.equal(x.get('input').value, current);
    assert.deepEqual(x.report(), currentReport);
    assert.equal(x.get('analyze').disabled, false);
  });
}

test('an older completion cannot enable Inspect during a newer file read', async () => {
  const x = runtime(), first = deferred(), second = deferred();
  const a = x.fixture(), b = x.fixture(); a.id = 'OLDER'; b.id = 'NEWER';
  const readA = x.choose(x.file('', { size: 500, promise: first.promise }));
  const readB = x.choose(x.file('', { size: 500, promise: second.promise }));
  first.resolve(bytes(JSON.stringify(a))); await readA;
  assert.equal(x.get('input').value, '');
  assert.equal(x.get('analyze').disabled, true);
  assert.equal(x.get('download').disabled, true);
  second.resolve(bytes(JSON.stringify(b))); await readB;
  assert.equal(x.report().id, b.id);
  assert.equal(x.get('analyze').disabled, false);
});

test('an older rejection cannot erase a newer error', async () => {
  const x = runtime(), pending = deferred();
  const read = x.choose(x.file('', { size: 500, promise: pending.promise }));
  await x.edit('{'); await x.inspect();
  const error = x.get('error').textContent;
  pending.reject(new Error('Stale failure')); await read;
  assert.equal(x.get('error').textContent, error);
  assert.equal(x.get('analyze').disabled, false);
});

for (const method of ['paste', 'file']) {
  test('one leading BOM is accepted and two are rejected through ' + method, async () => {
    const x = runtime(), raw = JSON.stringify(x.fixture());
    const supply = async text => {
      if (method === 'file') await x.choose(x.file(text));
      else { await x.edit(text); await x.inspect(); }
    };
    await supply('\ufeff' + raw);
    assert(x.report());
    await supply('\ufeff\ufeff' + raw);
    assert.equal(x.report(), null);
    assert(x.get('error').textContent.length > 0);
    assert.equal(x.get('download').disabled, true);
  });
  test('BOM bytes count toward the original byte limit through ' + method, async () => {
    const x = runtime(), raw = JSON.stringify(x.fixture());
    const atLimit = '\ufeff' + ' '.repeat(100000 - 3 - Buffer.byteLength(raw)) + raw;
    assert.equal(Buffer.byteLength(atLimit), 100000);
    const supply = async text => {
      if (method === 'file') await x.choose(x.file(text));
      else { await x.edit(text); await x.inspect(); }
    };
    await supply(atLimit); assert(x.report());
    await supply(atLimit + ' ');
    assert.equal(x.report(), null);
    assert.match(x.get('error').textContent, /100 KB/);
    assert.equal(x.get('download').disabled, true);
  });
}

for (const fault of ['url', 'click']) {
  test('download failure is visible, cleaned and retryable: ' + fault, async () => {
    const faults = { [fault]: true }, x = runtime(faults);
    await x.edit(x.fixture()); await x.inspect();
    await x.get('download').click();
    assert.match(x.get('error').textContent, /Cannot download/);
    x.flushTimers();
    assert.equal(x.created.length, x.revoked.length);
    faults[fault] = false;
    await x.get('download').click();
    assert.equal(x.get('error').textContent, '');
    x.flushTimers();
    assert.equal(x.created.length, x.revoked.length);
  });
}

test('untrusted markup stays text and survives report serialization', async () => {
  const x = runtime(), record = x.fixture();
  const payload = '</script><img src="https://example.invalid/" onerror="globalThis.executed=1">\u2028\u2029```';
  record.title = payload;
  record.correction.content = payload;
  record.initial.outcome.evidence = payload;
  await x.edit(record); await x.inspect();
  assert.equal(x.report().case.correction.content, payload);
  assert(x.get('result').textContent.includes(payload));
  assert.equal(x.context.executed, undefined);
  assert.deepEqual(x.networkCalls, []);
});

test('unknown declarations agree with visible text', async () => {
  const x = runtime(), record = x.fixture();
  record.correction.visible_to_later = null; delete record.comparison;
  await x.edit(record); await x.inspect();
  assert.equal(x.report().comparison_declared, null);
  assert(x.get('result').textContent.includes('Declared comparable: unknown'));
  assert(x.get('result').textContent.includes('Declared correction visibility: unknown'));
});

test('the built CSP hashes match its inline script and style', () => {
  const csp = html.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)[1];
  const style = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  for (const text of [script, style]) {
    assert(csp.includes(crypto.createHash('sha256').update(text).digest('base64')));
  }
  assert(csp.includes("connect-src &#x27;none&#x27;"));
});

(async () => {
  let failed = 0;
  for (const { name, run } of tests) {
    try { await run(); console.log('ok - ' + name); }
    catch (error) { failed++; console.error('not ok - ' + name + '\n' + error.stack); }
  }
  console.log(`${tests.length - failed}/${tests.length} state checks passed (mock DOM limits apply).`);
  if (failed) process.exitCode = 1;
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
