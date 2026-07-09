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
 * It also fails when CSS custom properties are defined outside their owners:
 *   - app tokens and compatibility aliases: src/styles/_variables.scss
 *   - glass tokens only: src/styles/_glass-system.scss
 *
 * Allowlist:
 *   - max-width queries with `orientation` (mixins can't express those)
 *   - max-width: 400px / 480px (intentional sub-mobile phones)
 *
 * Canonical tokens live in docs/frontend-overhaul-token-scss-plan.md,
 * src/styles/_variables.scss and src/styles/_glass-system.scss.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', 'src');
const APP_TOKEN_FILE = path.join(ROOT, 'styles', '_variables.scss');
const GLASS_TOKEN_FILE = path.join(ROOT, 'styles', '_glass-system.scss');
const TOKEN_ALLOWLIST = require('./design-token-allowlist.json');
const APP_TOKEN_ALLOWLIST = new Set(TOKEN_ALLOWLIST.appTokens);
const GLASS_TOKEN_ALLOWLIST = new Set(TOKEN_ALLOWLIST.glassTokens);

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/;
const MIN_WIDTH_RE = /@media[^{]*\bmin-width\s*:\s*\d+px/;
const TRANSITION_RE = /transition\s*:\s*[^;]*\b\d+(?:\.\d+)?(?:s|ms)\b/;
const CUSTOM_PROPERTY_DEFINITION_RE = /^\s*(--[A-Za-z0-9_-]+)\s*:/;

// Allow specific edge-case @media queries we can't express via mixins.
const ALLOWED_MEDIA = [
  /\borientation\s*:/,        // orientation queries
  /max-width\s*:\s*400px/,    // sub-iPhone-SE
  /max-width\s*:\s*480px/,    // small phones edge
  /max-width\s*:\s*767px/,    // explicit max in mixin gap, tolerated
];

function* walkVueFiles(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walkVueFiles(p);
    else if (entry.isFile() && p.endsWith('.vue')) yield p;
  }
}

function* walkStyleSources(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walkStyleSources(p);
    else if (entry.isFile() && /\.(vue|scss|css)$/.test(p)) yield p;
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

function checkCustomPropertyDefinition(file, lineNo, text, prop) {
  const rel = path.relative(path.resolve(__dirname, '..'), file);
  const inAppOwner = file === APP_TOKEN_FILE;
  const inGlassOwner = file === GLASS_TOKEN_FILE;

  if (!inAppOwner && !inGlassOwner) {
    violations.push({ file: rel, line: lineNo, kind: 'custom-property-definition', text });
    return;
  }

  if (inAppOwner) {
    if (prop.startsWith('--glass-')) {
      violations.push({ file: rel, line: lineNo, kind: 'glass-owner', text });
      return;
    }
    if (!APP_TOKEN_ALLOWLIST.has(prop)) {
      violations.push({ file: rel, line: lineNo, kind: 'unexpected-app-token', text });
    }
    return;
  }

  if (!prop.startsWith('--glass-')) {
    violations.push({ file: rel, line: lineNo, kind: 'app-owner', text });
    return;
  }
  if (!GLASS_TOKEN_ALLOWLIST.has(prop)) {
    violations.push({ file: rel, line: lineNo, kind: 'unexpected-glass-token', text });
  }
}

for (const file of walkStyleSources(ROOT)) {
  const src = fs.readFileSync(file, 'utf8');

  if (file.endsWith('.vue')) {
    for (const block of extractStyleBlocks(src)) {
      const lines = block.content.split('\n');
      lines.forEach((line, i) => {
        if (isCommented(line)) return;
        const m = line.match(CUSTOM_PROPERTY_DEFINITION_RE);
        if (m) checkCustomPropertyDefinition(file, block.startLine + i, line.trim(), m[1]);
      });
    }
    continue;
  }

  src.split('\n').forEach((line, i) => {
    if (isCommented(line)) return;
    const m = line.match(CUSTOM_PROPERTY_DEFINITION_RE);
    if (m) checkCustomPropertyDefinition(file, i + 1, line.trim(), m[1]);
  });
}

for (const file of walkVueFiles(ROOT)) {
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
  'custom-property-definition': 'Do not define CSS custom properties in components or non-owner SCSS. Use canonical tokens instead.',
  'glass-owner': 'Glass tokens belong in src/styles/_glass-system.scss, not _variables.scss.',
  'app-owner': 'App tokens belong in src/styles/_variables.scss. _glass-system.scss may define only --glass-* tokens.',
  'unexpected-app-token': 'New app token names must be intentional: document the canonical group and update scripts/design-token-allowlist.json.',
  'unexpected-glass-token': 'New glass token names must be intentional: document the glass group and update scripts/design-token-allowlist.json.',
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
