#!/usr/bin/env node

const fs = require('fs');
const yaml = require('js-yaml');
const core = require('@actions/core');

const COMPLETION_RE = /^(?<addr>\S[^:]*):\s+(?<verb>Creation complete|Modifications complete|Destruction complete).*$/;

// ---------- Console log processing ----------

// Replicates the awk pipeline in the original "Format Terraform Apply Diff"
// step: drops "Warning:" blocks tied to -target, and trims everything from the
// final ─── divider onward.
function stripConsoleLog(consoleText) {
  let skip = 0;
  const stage1 = [];
  for (const line of consoleText.split('\n')) {
    if (/^Warning:/.test(line)) { skip = 1; continue; }
    if (skip && (/^Note that the -target option/.test(line) || /^The -target option/.test(line))) {
      skip = 2;
      continue;
    }
    if (skip === 2 && line.trim() === '') {
      skip = 0;
      continue;
    }
    if (skip) continue;
    stage1.push(line);
  }

  const stage2 = [];
  for (const line of stage1) {
    if (/^─────/.test(line)) break;
    stage2.push(line);
  }
  return stage2.join('\n');
}

// Extracts the summary line(s) the original awk used as the <details> heading.
function extractSummary(consoleText) {
  return consoleText
    .split('\n')
    .filter(l => /^(Error:|Plan:|Apply complete!|No changes\.|Success)/.test(l))
    .join('\n');
}

// Builds the +/-/!/~/# diff block from the plan console output, replacing the
// original `grep '^  # ' | sed ...` pipeline.
function buildDiff(consoleText) {
  const lines = consoleText
    .split('\n')
    .filter(l => l.startsWith('  # '))
    .map(l => l.slice(4))
    .map(l => {
      if (/ be created$/.test(l)) return `+ ${l}`;
      if (/ be destroyed$/.test(l)) return `- ${l}`;
      if (/ be updated| be replaced$/.test(l)) return `! ${l}`;
      if (/ be read$/.test(l)) return `~ ${l}`;
      return `# ${l}`;
    });
  return lines.length === 0 ? 'No changes detected' : lines.join('\n');
}

// ---------- Outputs section ----------

function loadOutputsConfig(configPath) {
  if (!fs.existsSync(configPath)) return {};
  const data = yaml.load(fs.readFileSync(configPath, 'utf8')) || {};
  const outputs = data.outputs || {};
  if (typeof outputs !== 'object' || Array.isArray(outputs)) {
    throw new Error(`'outputs' in ${configPath} must be a mapping`);
  }
  return outputs;
}

function parseCompletionLines(consoleText) {
  const completions = {};
  for (const line of consoleText.split('\n')) {
    const m = COMPLETION_RE.exec(line);
    if (m) completions[m.groups.addr.trim()] = line.trim();
  }
  return completions;
}

function* iterResources(state) {
  function* walk(module) {
    for (const r of module.resources || []) {
      if (r.mode && r.mode !== 'managed') continue;
      yield { address: r.address, type: r.type, values: r.values || {} };
    }
    for (const child of module.child_modules || []) yield* walk(child);
  }
  yield* walk((state.values && state.values.root_module) || {});
}

function formatAttrs(values, attrs) {
  const width = attrs.reduce((m, a) => Math.max(m, a.length), 0);
  return attrs.map(a => {
    const v = values[a];
    const vStr = v === undefined || v === null ? 'null' : JSON.stringify(v);
    return `${a.padEnd(width)} = ${vStr}`;
  });
}

function renderOutputs(outputsCfg, state, completions) {
  // Only render resources that were actually applied in this run, identified
  // by the presence of a Creation/Modifications/Destruction completion line.
  const blocks = [];
  for (const { address, type, values } of iterResources(state)) {
    if (!(address in completions)) continue;
    const attrs = outputsCfg[type];
    if (!attrs) continue;
    const header = completions[address];
    const attrLines = formatAttrs(values, attrs);
    blocks.push(
      `- <code>${header}</code>\n<pre>\n` +
      attrLines.join('\n') +
      `\n</pre>`
    );
  }
  if (blocks.length === 0) return '';
  return `<h4>Outputs</h4>\n\n${blocks.join('\n\n')}\n\n`;
}

// ---------- Body building ----------

function buildApplyBody({ directory, runUrl, duration, cmd, summary, cleanConsole, outputs }) {
  const summaryLine = summary || 'View output for details';
  const outputsBlock = outputs ? `\n${outputs}\n` : '';
  return `**Terraform apply** (Okta ${directory}) ran in [${duration} seconds](${runUrl}).
\`\`\`
${cmd}
\`\`\`

<details>
<summary>${summaryLine}</summary>

\`\`\`
${cleanConsole}
\`\`\`
</details>
${outputsBlock}
---
📌 _Reminder to validate the configuration was applied correctly, then **merge this PR** to release the deployment lock._
`;
}

function buildPlanBody({ directory, runUrl, duration, cmd, summary, cleanConsole, diff, mixedImport }) {
  const summaryLine = summary || 'View output for details';
  const warning = mixedImport
    ? `> [!CAUTION]
> **This PR mixes import operations with other changes.** PRs containing imports must contain *only* imports (no creates, updates, or deletes). Please split this PR so the imports land separately from the other changes. The plan will not pass until this is resolved.

`
    : '';
  return `**Terraform plan** (Okta ${directory}) ran in [${duration} seconds](${runUrl}).
${warning}\`\`\`
${cmd}
\`\`\`

#### Diff of changes
\`\`\`diff
${diff}
\`\`\`

<details>
<summary>${summaryLine}</summary>

\`\`\`
${cleanConsole}
\`\`\`
</details>
`;
}

function buildFailureBody({ mode, directory, runUrl }) {
  const verb = mode === 'plan' ? 'plan' : 'apply';
  return `**Terraform ${verb}** (Okta ${directory}) [failed](${runUrl}).`;
}

// ---------- Main ----------

function main() {
  const mode = (core.getInput('mode') || 'apply').toLowerCase();
  if (mode !== 'plan' && mode !== 'apply') {
    throw new Error(`mode must be 'plan' or 'apply', got: ${mode}`);
  }

  const directory = core.getInput('directory', { required: true });
  const consolePath = core.getInput('console_path', { required: true });
  const jobStatus = core.getInput('job_status', { required: true });

  const serverUrl = process.env.GITHUB_SERVER_URL || 'https://github.com';
  const repository = process.env.GITHUB_REPOSITORY || '';
  const runId = process.env.GITHUB_RUN_ID || '';
  const runUrl = `${serverUrl}/${repository}/actions/runs/${runId}`;

  let body;
  if (jobStatus === 'failure') {
    body = buildFailureBody({ mode, directory, runUrl });
  } else {
    const duration = core.getInput('duration');
    const cmd = core.getInput('cmd');

    if (!fs.existsSync(consolePath)) {
      throw new Error(`console_path not found: ${consolePath}`);
    }

    const consoleText = fs.readFileSync(consolePath, 'utf8');
    const cleanConsole = stripConsoleLog(consoleText);
    const summary = extractSummary(consoleText);

    if (mode === 'plan') {
      const diff = buildDiff(consoleText);
      const mixedImport = (core.getInput('mixed_import') || '').toLowerCase() === 'true';
      body = buildPlanBody({ directory, runUrl, duration, cmd, summary, cleanConsole, diff, mixedImport });
    } else {
      const configPath = core.getInput('config_path') || '.terraform-ci.yaml';
      const statePath = core.getInput('state_path');

      let outputs = '';
      if (statePath && fs.existsSync(statePath)) {
        const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
        const outputsCfg = loadOutputsConfig(configPath);
        const completions = parseCompletionLines(consoleText);
        outputs = renderOutputs(outputsCfg, state, completions);
      }

      body = buildApplyBody({ directory, runUrl, duration, cmd, summary, cleanConsole, outputs });
    }
  }

  const bodyPath = core.getInput('body_path');
  if (bodyPath) {
    fs.writeFileSync(bodyPath, body);
    core.setOutput('body_path', bodyPath);
  } else {
    core.setOutput('body', body);
  }
}

try {
  main();
} catch (err) {
  core.setFailed(err.message);
}
