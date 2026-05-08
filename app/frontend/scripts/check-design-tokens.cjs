#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Design Token Lint
 * ------------------------------------------------------------
 * Fails CI when a .vue <style> block contains:
 *   - hardcoded hex colors          (#fff, #abc123, ...)
 *   - hardcoded breakpoints         (@media (min-width: 768px) ...)
 *   - hardcoded transition timings  (transition: ... 0.3s ease)
 *
 * Allowlist:
 *   - max-width queries with `orientation` (mixins can't express those)
 *   - max-width: 400px / 480px (intentional sub-mobile phones)
 *
 * Tokens to use instead live in app/frontend/src/styles/_variables.scss
 * and the respond-to/respond-below mixins in _mixins.scss.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', 'src');

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/;
const MIN_WIDTH_RE = /@media[^{]*\bmin-width\s*:\s*\d+px/;
const TRANSITION_RE = /transition\s*:\s*[^;]*\b\d+(?:\.\d+)?(?:s|ms)\b/;

// Allow specific edge-case @media queries we can't express via mixins.
const ALLOWED_MEDIA = [
  /\borientation\s*:/,        // orientation queries
  /max-width\s*:\s*400px/,    // sub-iPhone-SE
  /max-width\s*:\s*480px/,    // small phones edge
  /max-width\s*:\s*767px/,    // explicit max in mixin gap, tolerated
];

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(p);
    else if (entry.isFile() && p.endsWith('.vue')) yield p;
  }
}

function extractStyleBlocks(src) {
  const blocks = [];
  const re = /<style\b[^>]*>([\s\S]*?)<\/style>/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    // Track starting line number of the block content
    const before = src.slice(0, m.index + m[0].indexOf('>') + 1);
    const startLine = before.split('\n').length;
    blocks.push({ content: m[1], startLine });
  }
  return blocks;
}

function lineAllowed(line, kind) {
  if (kind === 'media') {
    return ALLOWED_MEDIA.some((rx) => rx.test(line));
  }
  return false;
}

function isCommented(line) {
  const trimmed = line.trim();
  return trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*');
}

const violations = [];

for (const file of walk(ROOT)) {
  // Skip the design-system itself
  if (file.includes(`${path.sep}styles${path.sep}`)) continue;

  const src = fs.readFileSync(file, 'utf8');
  const blocks = extractStyleBlocks(src);
  const rel = path.relative(path.resolve(__dirname, '..'), file);

  for (const block of blocks) {
    const lines = block.content.split('\n');
    lines.forEach((line, i) => {
      if (isCommented(line)) return;
      const lineNo = block.startLine + i;

      if (HEX_RE.test(line)) {
        violations.push({ file: rel, line: lineNo, kind: 'hex', text: line.trim() });
      }
      if (MIN_WIDTH_RE.test(line) && !lineAllowed(line, 'media')) {
        violations.push({ file: rel, line: lineNo, kind: 'breakpoint', text: line.trim() });
      }
      if (TRANSITION_RE.test(line)) {
        violations.push({ file: rel, line: lineNo, kind: 'transition', text: line.trim() });
      }
    });
  }
}

if (violations.length === 0) {
  console.log('✅ design-token lint: no violations');
  process.exit(0);
}

const byKind = violations.reduce((acc, v) => {
  (acc[v.kind] ||= []).push(v);
  return acc;
}, {});

const HINTS = {
  hex: 'Use a CSS variable from src/styles/_variables.scss (e.g. var(--primary-color)).',
  breakpoint: "Use the respond-to / respond-below mixins, e.g. @include m.respond-to('md').",
  transition: 'Use --transition-base / --transition-fast / --transition-slow or var(--duration-*) + var(--ease-*).',
};

console.error('❌ design-token lint failed\n');
for (const [kind, list] of Object.entries(byKind)) {
  console.error(`  ${kind} (${list.length}):`);
  console.error(`    hint: ${HINTS[kind]}`);
  for (const v of list.slice(0, 30)) {
    console.error(`    ${v.file}:${v.line}  ${v.text}`);
  }
  if (list.length > 30) console.error(`    ... and ${list.length - 30} more`);
  console.error('');
}
console.error(`total violations: ${violations.length}`);
process.exit(1);
