#!/usr/bin/env node

const fs = require('fs');
const core = require('@actions/core');

const { classify, loadAllowedFromFile } = require('./lib');

function main() {
  const planPath = process.env.INPUT_PLAN_FILE;
  const configPath = process.env.INPUT_CONFIG_FILE;

  if (!planPath) throw new Error('plan_file input is required');
  if (!fs.existsSync(planPath)) throw new Error(`plan_file not found: ${planPath}`);

  const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
  const allowed = loadAllowedFromFile(configPath);

  const { targets, imports, others, ignored, isMixed } = classify(plan, allowed);

  console.log(`imports=${imports.length} others=${others.length} ignored=${ignored.length} total_targets=${targets.length}`);
  if (imports.length) console.log(`  imports: ${imports.join(', ')}`);
  if (others.length) console.log(`  others:  ${others.join(', ')}`);
  if (ignored.length) console.log(`  ignored: ${ignored.join(', ')}`);

  core.setOutput('targets', `'${targets.join(' ')}'`);
  core.setOutput('has_changes', targets.length > 0 ? 'true' : 'false');
  core.setOutput('is_mixed_import', isMixed ? 'true' : 'false');
  core.setOutput('imports_count', String(imports.length));
  core.setOutput('others_count', String(others.length));
}

try {
  main();
} catch (err) {
  core.setFailed(err.message);
}
