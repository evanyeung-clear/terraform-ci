#!/usr/bin/env node

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const {
  classify,
  isIgnorableUpdate,
  isNoOp,
  isNullish,
  deepEqual,
  normalizeAllowed,
  loadAllowedFromFile,
} = require('./lib');

// ---- helpers ---------------------------------------------------------------

function rc({ address, type = 'okta_app_oauth', actions = ['update'], importing = false, before = null, after = null }) {
  return {
    address,
    type,
    change: {
      actions,
      before,
      after,
      ...(importing ? { importing: { id: 'abc' } } : {}),
    },
  };
}

// ---- deepEqual -------------------------------------------------------------

test('deepEqual: primitives', () => {
  assert.equal(deepEqual(1, 1), true);
  assert.equal(deepEqual('a', 'a'), true);
  assert.equal(deepEqual(1, 2), false);
  assert.equal(deepEqual(null, null), true);
  assert.equal(deepEqual(null, undefined), true);
  assert.equal(deepEqual(null, 0), false);
});

test('deepEqual: arrays', () => {
  assert.equal(deepEqual([1, 2, 3], [1, 2, 3]), true);
  assert.equal(deepEqual([1, 2], [1, 2, 3]), false);
  assert.equal(deepEqual([{ a: 1 }], [{ a: 1 }]), true);
  assert.equal(deepEqual([{ a: 1 }], [{ a: 2 }]), false);
});

test('deepEqual: objects', () => {
  assert.equal(deepEqual({ a: 1, b: 2 }, { b: 2, a: 1 }), true);
  assert.equal(deepEqual({ a: 1 }, { a: 1, b: 2 }), false);
  assert.equal(deepEqual({ a: { b: [1] } }, { a: { b: [1] } }), true);
  assert.equal(deepEqual({ a: { b: [1] } }, { a: { b: [2] } }), false);
});

test('deepEqual: type mismatch', () => {
  assert.equal(deepEqual([], {}), false);
  assert.equal(deepEqual('1', 1), false);
});

// ---- isNullish -------------------------------------------------------------

test('isNullish', () => {
  assert.equal(isNullish(null), true);
  assert.equal(isNullish(undefined), true);
  assert.equal(isNullish(0), false);
  assert.equal(isNullish(''), false);
  assert.equal(isNullish(false), false);
});

// ---- isNoOp ----------------------------------------------------------------

test('isNoOp', () => {
  assert.equal(isNoOp([]), true);
  assert.equal(isNoOp(null), true);
  assert.equal(isNoOp(undefined), true);
  assert.equal(isNoOp(['no-op']), true);
  assert.equal(isNoOp(['noop']), true);
  assert.equal(isNoOp(['no-op', 'no-op']), true);
  assert.equal(isNoOp(['update']), false);
  assert.equal(isNoOp(['create']), false);
  assert.equal(isNoOp(['no-op', 'update']), false);
});

// ---- normalizeAllowed ------------------------------------------------------

test('normalizeAllowed: empty / invalid', () => {
  assert.deepEqual(normalizeAllowed(null), {});
  assert.deepEqual(normalizeAllowed(undefined), {});
  assert.deepEqual(normalizeAllowed('string'), {});
  assert.deepEqual(normalizeAllowed({}), {});
});

test('normalizeAllowed: scalar value becomes array', () => {
  const out = normalizeAllowed({
    okta_app_oauth: { omit_secret: false, refresh_token_rotation: 'STATIC' },
  });
  assert.deepEqual(out, {
    okta_app_oauth: {
      omit_secret: [false],
      refresh_token_rotation: ['STATIC'],
    },
  });
});

test('normalizeAllowed: array value preserved', () => {
  const out = normalizeAllowed({
    okta_app_oauth: { refresh_token_rotation: ['STATIC', 'DYNAMIC'] },
  });
  assert.deepEqual(out, {
    okta_app_oauth: { refresh_token_rotation: ['STATIC', 'DYNAMIC'] },
  });
});

test('normalizeAllowed: skips non-object attribute groups', () => {
  const out = normalizeAllowed({
    okta_app_oauth: { ok: 1 },
    bad: 'not an object',
  });
  assert.deepEqual(out, { okta_app_oauth: { ok: [1] } });
});

// ---- loadAllowedFromFile ---------------------------------------------------

test('loadAllowedFromFile: missing path returns {}', () => {
  assert.deepEqual(loadAllowedFromFile(''), {});
  assert.deepEqual(loadAllowedFromFile('/nonexistent/path/zzz.yaml'), {});
});

test('loadAllowedFromFile: reads and normalizes yaml', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'classify-test-'));
  const file = path.join(dir, '.terraform-ci.yaml');
  fs.writeFileSync(
    file,
    'mixed_import_allowed_additions:\n' +
    '  okta_app_oauth:\n' +
    '    omit_secret: false\n' +
    '    refresh_token_leeway: 0\n' +
    '    refresh_token_rotation: STATIC\n'
  );
  try {
    const out = loadAllowedFromFile(file);
    assert.deepEqual(out, {
      okta_app_oauth: {
        omit_secret: [false],
        refresh_token_leeway: [0],
        refresh_token_rotation: ['STATIC'],
      },
    });
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('loadAllowedFromFile: empty yaml returns {}', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'classify-test-'));
  const file = path.join(dir, '.terraform-ci.yaml');
  fs.writeFileSync(file, '');
  try {
    assert.deepEqual(loadAllowedFromFile(file), {});
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// ---- isIgnorableUpdate -----------------------------------------------------

const allowed = normalizeAllowed({
  okta_app_oauth: {
    omit_secret: false,
    refresh_token_leeway: 0,
    refresh_token_rotation: 'STATIC',
  },
});

test('isIgnorableUpdate: no rules for type', () => {
  const r = rc({
    address: 'aws_s3_bucket.x',
    type: 'aws_s3_bucket',
    before: { name: null },
    after: { name: 'foo' },
  });
  assert.equal(isIgnorableUpdate(r, allowed), false);
});

test('isIgnorableUpdate: addition matching allowlist', () => {
  const r = rc({
    address: 'okta_app_oauth.x',
    before: { omit_secret: null, refresh_token_leeway: null },
    after: { omit_secret: false, refresh_token_leeway: 0 },
  });
  assert.equal(isIgnorableUpdate(r, allowed), true);
});

test('isIgnorableUpdate: addition not in allowlist', () => {
  const r = rc({
    address: 'okta_app_oauth.x',
    before: { omit_secret: null },
    after: { omit_secret: true },
  });
  assert.equal(isIgnorableUpdate(r, allowed), false);
});

test('isIgnorableUpdate: from-to modification rejected', () => {
  const r = rc({
    address: 'okta_app_oauth.x',
    before: { refresh_token_rotation: 'STATIC' },
    after: { refresh_token_rotation: 'DYNAMIC' },
  });
  assert.equal(isIgnorableUpdate(r, allowed), false);
});

test('isIgnorableUpdate: attribute not in rules but changed', () => {
  const r = rc({
    address: 'okta_app_oauth.x',
    before: { omit_secret: null, label: null },
    after: { omit_secret: false, label: 'My App' },
  });
  assert.equal(isIgnorableUpdate(r, allowed), false);
});

test('isIgnorableUpdate: no diffs at all returns false', () => {
  const r = rc({
    address: 'okta_app_oauth.x',
    before: { omit_secret: false },
    after: { omit_secret: false },
  });
  assert.equal(isIgnorableUpdate(r, allowed), false);
});

test('isIgnorableUpdate: undefined before treated as nullish', () => {
  const r = rc({
    address: 'okta_app_oauth.x',
    before: {},
    after: { omit_secret: false },
  });
  assert.equal(isIgnorableUpdate(r, allowed), true);
});

// ---- classify --------------------------------------------------------------

test('classify: empty plan', () => {
  assert.deepEqual(classify({}, {}), {
    targets: [], imports: [], others: [], ignored: [], isMixed: false,
  });
  assert.deepEqual(classify({ resource_changes: [] }, {}), {
    targets: [], imports: [], others: [], ignored: [], isMixed: false,
  });
  assert.deepEqual(classify(null, {}), {
    targets: [], imports: [], others: [], ignored: [], isMixed: false,
  });
});

test('classify: skips no-ops', () => {
  const plan = {
    resource_changes: [
      rc({ address: 'okta_app_oauth.a', actions: ['no-op'] }),
      rc({ address: 'okta_app_oauth.b', actions: [] }),
    ],
  };
  const out = classify(plan, {});
  assert.deepEqual(out.targets, []);
  assert.equal(out.isMixed, false);
});

test('classify: imports only', () => {
  const plan = {
    resource_changes: [
      rc({ address: 'okta_app_oauth.a', actions: ['no-op'], importing: true }),
      rc({ address: 'okta_app_oauth.b', actions: ['no-op'], importing: true }),
    ],
  };
  const out = classify(plan, {});
  assert.deepEqual(out.imports, ['okta_app_oauth.a', 'okta_app_oauth.b']);
  assert.deepEqual(out.others, []);
  assert.deepEqual(out.targets, ['-target=okta_app_oauth.a', '-target=okta_app_oauth.b']);
  assert.equal(out.isMixed, false);
});

test('classify: changes only', () => {
  const plan = {
    resource_changes: [
      rc({
        address: 'okta_app_oauth.a',
        actions: ['create'],
        before: null,
        after: { label: 'A' },
      }),
    ],
  };
  const out = classify(plan, {});
  assert.deepEqual(out.others, ['okta_app_oauth.a']);
  assert.deepEqual(out.imports, []);
  assert.equal(out.isMixed, false);
});

test('classify: mixed import (no allowlist)', () => {
  const plan = {
    resource_changes: [
      rc({ address: 'okta_app_oauth.a', actions: ['no-op'], importing: true }),
      rc({
        address: 'okta_app_oauth.b',
        actions: ['update'],
        before: { refresh_token_rotation: 'STATIC' },
        after: { refresh_token_rotation: 'DYNAMIC' },
      }),
    ],
  };
  const out = classify(plan, {});
  assert.deepEqual(out.imports, ['okta_app_oauth.a']);
  assert.deepEqual(out.others, ['okta_app_oauth.b']);
  assert.deepEqual(out.ignored, []);
  assert.equal(out.isMixed, true);
});

test('classify: mixed import becomes non-mixed via allowlist', () => {
  const plan = {
    resource_changes: [
      rc({ address: 'okta_app_oauth.a', actions: ['no-op'], importing: true }),
      rc({
        address: 'okta_app_oauth.b',
        actions: ['update'],
        before: { omit_secret: null, refresh_token_leeway: null },
        after: { omit_secret: false, refresh_token_leeway: 0 },
      }),
    ],
  };
  const out = classify(plan, allowed);
  assert.deepEqual(out.imports, ['okta_app_oauth.a']);
  assert.deepEqual(out.ignored, ['okta_app_oauth.b']);
  assert.deepEqual(out.others, []);
  assert.equal(out.isMixed, false);
});

test('classify: still mixed when modification is from-to even with allowlist', () => {
  const plan = {
    resource_changes: [
      rc({ address: 'okta_app_oauth.a', actions: ['no-op'], importing: true }),
      rc({
        address: 'okta_app_oauth.b',
        actions: ['update'],
        before: { refresh_token_rotation: 'STATIC' },
        after: { refresh_token_rotation: 'DYNAMIC' },
      }),
    ],
  };
  const out = classify(plan, allowed);
  assert.deepEqual(out.imports, ['okta_app_oauth.a']);
  assert.deepEqual(out.others, ['okta_app_oauth.b']);
  assert.deepEqual(out.ignored, []);
  assert.equal(out.isMixed, true);
});

test('classify: targets list includes every non-no-op address', () => {
  const plan = {
    resource_changes: [
      rc({ address: 'okta_app_oauth.a', actions: ['no-op'], importing: true }),
      rc({ address: 'okta_app_oauth.b', actions: ['no-op'] }), // skipped
      rc({
        address: 'okta_app_oauth.c',
        actions: ['create'],
        before: null,
        after: { label: 'C' },
      }),
    ],
  };
  const out = classify(plan, {});
  assert.deepEqual(out.targets, [
    '-target=okta_app_oauth.a',
    '-target=okta_app_oauth.c',
  ]);
});
