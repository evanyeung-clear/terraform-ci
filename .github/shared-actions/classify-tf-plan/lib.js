// Pure classification logic — no GitHub Actions or filesystem dependencies
// so it can be unit-tested directly.

const fs = require('fs');
const yaml = require('js-yaml');

function deepEqual(a, b) {
  if (a === b) return true;
  if (a === null || a === undefined || b === null || b === undefined) {
    return (a === null || a === undefined) && (b === null || b === undefined);
  }
  if (typeof a !== typeof b) return false;
  if (typeof a !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a)) {
    if (a.length !== b.length) return false;
    return a.every((x, i) => deepEqual(x, b[i]));
  }
  const ak = Object.keys(a);
  const bk = Object.keys(b);
  if (ak.length !== bk.length) return false;
  return ak.every(k => deepEqual(a[k], b[k]));
}

function isNullish(v) {
  return v === null || v === undefined;
}

function isNoOp(actions) {
  return !actions || actions.length === 0 || actions.every(a => a === 'no-op' || a === 'noop');
}

// Normalize the optional `mixed_import_allowed_additions` config block into
// `{ resource_type: { attribute: [allowed_values...] } }`.
function normalizeAllowed(raw) {
  const out = {};
  if (!raw || typeof raw !== 'object') return out;
  for (const [type, attrs] of Object.entries(raw)) {
    if (!attrs || typeof attrs !== 'object') continue;
    out[type] = {};
    for (const [attr, val] of Object.entries(attrs)) {
      out[type][attr] = Array.isArray(val) ? val : [val];
    }
  }
  return out;
}

function loadAllowedFromFile(configPath) {
  if (!configPath || !fs.existsSync(configPath)) return {};
  const data = yaml.load(fs.readFileSync(configPath, 'utf8')) || {};
  return normalizeAllowed(data.mixed_import_allowed_additions);
}

// A non-import resource_change is "ignorable" if every attribute diff is an
// addition (before is null/missing) AND the new value is in the allowlist
// for that resource type + attribute. A from-to modification is never
// ignorable.
function isIgnorableUpdate(rc, allowed) {
  const rules = allowed[rc.type];
  if (!rules) return false;

  const before = rc.change.before || {};
  const after = rc.change.after || {};

  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  let sawDiff = false;
  for (const k of keys) {
    if (deepEqual(before[k], after[k])) continue;
    sawDiff = true;
    if (!isNullish(before[k])) return false;
    const allowedValues = rules[k];
    if (!allowedValues) return false;
    if (!allowedValues.some(v => deepEqual(v, after[k]))) return false;
  }
  return sawDiff;
}

// Classify a plan into targets, imports, others, and ignored buckets.
// `allowed` is the normalized allowlist (use normalizeAllowed first if you
// have a raw config object).
function classify(plan, allowed) {
  const targets = [];
  const imports = [];
  const others = [];
  const ignored = [];

  for (const rc of (plan && plan.resource_changes) || []) {
    const change = rc.change || {};
    const actions = change.actions || [];
    const isImport = !!change.importing;

    if (isNoOp(actions) && !isImport) continue;

    targets.push(`-target=${rc.address}`);

    if (isImport) {
      imports.push(rc.address);
      continue;
    }
    if (isIgnorableUpdate(rc, allowed)) {
      ignored.push(rc.address);
      continue;
    }
    others.push(rc.address);
  }

  return {
    targets,
    imports,
    others,
    ignored,
    isMixed: imports.length > 0 && others.length > 0,
  };
}

module.exports = {
  classify,
  isIgnorableUpdate,
  isNoOp,
  isNullish,
  deepEqual,
  normalizeAllowed,
  loadAllowedFromFile,
};
