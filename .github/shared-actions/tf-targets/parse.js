#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const Parser = require('tree-sitter');
const HCL = require('@tree-sitter-grammars/tree-sitter-hcl');
const core = require('@actions/core');
const github = require('@actions/github');

const parser = new Parser();
parser.setLanguage(HCL);

function getGitDiffLines(baseBranch = 'main') {
  const output = execSync(
    // `git diff --unified=0 --no-color ${baseBranch} -- '*.tf'`,
    `git diff --relative --unified=0 --no-color $(git merge-base HEAD main) -- '*.tf'`,
    { encoding: 'utf-8' }
  );

  const fileLineMap = {};
  let currentFile = null;

  for (const line of output.split('\n')) {
    if (line.startsWith('+++ b/')) {
      currentFile = line.slice(6).trim();
    } else if (line.startsWith('@@') && currentFile) {
      const match = /\+(\d+)(?:,(\d+))?/.exec(line);
      if (match) {
        const start = parseInt(match[1]);
        const count = parseInt(match[2] || '1');
        const lines = Array.from({ length: count }, (_, i) => start + i);
        fileLineMap[currentFile] = (fileLineMap[currentFile] || []).concat(lines);
      }
    }
  }

  return fileLineMap;
}

function findChangedBlocks(filePath, changedLines) {
  const source = fs.readFileSync(filePath, 'utf8');
  const tree = parser.parse(source);
  const results = [];

  // Helper: Recursively find all block nodes
  function findBlockNodes(node, blocks = []) {
    if (node.type === 'block') {
      blocks.push(node);
    }

    for (const child of node.namedChildren || []) {
      findBlockNodes(child, blocks);
    }

    return blocks;
  }

  // Helper: Determine if a block overlaps with any changed line
  function nodeContainsLine(node, line) {
    return node.startPosition.row + 1 <= line && node.endPosition.row + 1 >= line;
  }

  const blockNodes = findBlockNodes(tree.rootNode);

  for (const block of blockNodes) {
    const [identifierNode, ...labelNodes] = block.namedChildren;

    if (!identifierNode || identifierNode.type !== 'identifier') continue;

    const blockType = source.slice(identifierNode.startIndex, identifierNode.endIndex);

    // Filter for specific block types
    if (!['resource', 'module'].includes(blockType)) continue;

    const blockLabels = labelNodes
      .filter(n => n.type === 'string_lit')
      .map(n => source.slice(n.startIndex, n.endIndex).replace(/"/g, ''));

    const blockName = blockLabels.join('.');

    const startLine = block.startPosition.row + 1;
    const endLine = block.endPosition.row + 1;

    const overlaps = changedLines.some(line => nodeContainsLine(block, line));

    if (overlaps) {
      results.push({
        blockType,
        blockName,
        startLine,
        endLine,
        body: source.slice(block.startIndex, block.endIndex),
      });
    }
  }

  return results;
}

function main() {
  const baseBranch = process.argv[2] || 'main';
  const changes = getGitDiffLines(baseBranch);

  const targets = new Set();

  for (const [file, lines] of Object.entries(changes)) {
    if (!fs.existsSync(file)) continue;

    const blocks = findChangedBlocks(file, lines);

    for (const block of blocks) {
      const key = block.blockName;
      if (targets.has(key)) { continue; } // Avoid duplicates

      targets.add(key);
    }
  }

  if (targets.size === 0) {
    console.log("No changed resource/module blocks detected.");
  } else {
    const targetString = (Array.from(targets).map(target => `-target="${target}"`).join(' '));
    core.info(`Detected changed Terraform targets:\n${targetString}`);
    core.setOutput("targets", targetString);
  }
}

main();