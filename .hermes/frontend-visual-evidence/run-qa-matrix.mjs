import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = require('playwright');
const axe = require('axe-core');

const baseURL = process.env.QA_BASE_URL || 'http://127.0.0.1:5173';
const outDir = path.resolve(process.env.QA_OUT_DIR || '../../.hermes/frontend-visual-evidence');
const viewports = [390, 430, 768, 1024, 1280, 1440];
const routes = [
  ['dashboard', '/'], ['streamers', '/streamers'], ['streamer-detail', '/streamers/1'],
  ['library', '/videos'], ['stored-player', '/videos/1'], ['live-player', '/live/streamer_alpha'],
  ['subscriptions', '/subscriptions'], ['settings', '/settings'], ['admin', '/admin'], ['add-streamer', '/add-streamer'],
];

async function waitForApp(page) {
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => null);
  await page.locator('#app').waitFor({ timeout: 20000 });
  await page.waitForTimeout(350);
}

async function collectVitals(page, routePath) {
  await page.addInitScript(() => {
    window.__qaVitals = { cls: 0, lcp: 0, inp: 0 };
    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.__qaVitals.cls += entry.value;
      }).observe({ type: 'layout-shift', buffered: true });
      new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const last = entries[entries.length - 1];
        if (last) window.__qaVitals.lcp = last.startTime;
      }).observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const latency = entry.processingStart - entry.startTime;
          if (latency > window.__qaVitals.inp) window.__qaVitals.inp = latency;
        }
      }).observe({ type: 'event', buffered: true, durationThreshold: 16 });
    } catch (error) {
      window.__qaVitals.error = String(error?.message || error);
    }
  });
  await page.goto(baseURL + routePath, { waitUntil: 'domcontentloaded' });
  await waitForApp(page);
  const button = page.locator('button').first();
  if (await button.count()) await button.click({ timeout: 2000 }).catch(() => null);
  await page.waitForTimeout(1200);
  return page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const paint = Object.fromEntries(performance.getEntriesByType('paint').map((entry) => [entry.name, entry.startTime]));
    return {
      fcp: Math.round(paint['first-contentful-paint'] || 0), firstPaint: Math.round(paint['first-paint'] || 0),
      lcp: Math.round(window.__qaVitals?.lcp || 0), cls: Number((window.__qaVitals?.cls || 0).toFixed(4)),
      inpApprox: Math.round(window.__qaVitals?.inp || 0), domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd) : 0,
      loadEventEnd: nav ? Math.round(nav.loadEventEnd) : 0, transferSize: nav ? nav.transferSize : 0,
      vitalsError: window.__qaVitals?.error || null,
    };
  });
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const routeResults = [], screenshots = [], axeResults = [], vitals = [];

  for (const width of viewports) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    for (const [name, routePath] of routes) {
      const row = { name, route: routePath, width, ok: false };
      try {
        await page.goto(baseURL + routePath, { waitUntil: 'domcontentloaded' });
        await waitForApp(page);
        const file = `${String(width).padStart(4, '0')}-${name}.png`;
        await page.screenshot({ path: path.join(outDir, file), fullPage: true });
        row.ok = true;
        row.screenshot = file;
        row.horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
        row.bodyTextStart = await page.locator('body').innerText({ timeout: 5000 }).then((t) => t.replace(/\s+/g, ' ').trim().slice(0, 180));
        screenshots.push(file);
      } catch (error) {
        row.error = String(error?.message || error);
      }
      routeResults.push(row);
    }
    await context.close();
  }

  for (const width of [390, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    for (const [name, routePath] of routes) {
      const row = { name, route: routePath, width };
      try {
        await page.goto(baseURL + routePath, { waitUntil: 'domcontentloaded' });
        await waitForApp(page);
        await page.addScriptTag({ content: axe.source });
        const result = await page.evaluate(async () => window.axe.run(document, { resultTypes: ['violations', 'incomplete'] }));
        row.violations = result.violations.map((v) => ({ id: v.id, impact: v.impact, description: v.description, nodes: v.nodes.length, targets: v.nodes.slice(0, 5).map((n) => n.target.join(' ')) }));
        row.incomplete = result.incomplete.length;
      } catch (error) {
        row.error = String(error?.message || error);
      }
      axeResults.push(row);
    }
    await context.close();
  }

  const keyboardContext = await browser.newContext({ viewport: { width: 390, height: 900 } });
  const keyboardPage = await keyboardContext.newPage();
  const keyboard = { route: '/', notificationDialog: false, focusMoved: false, escapeCloses: false, tabSequence: [] };
  try {
    await keyboardPage.goto(baseURL + '/', { waitUntil: 'domcontentloaded' });
    await waitForApp(keyboardPage);
    await keyboardPage.getByRole('button', { name: /notification/i }).first().click({ timeout: 5000 });
    await keyboardPage.locator('[role="dialog"]').first().waitFor({ timeout: 5000 });
    keyboard.notificationDialog = true;
    await keyboardPage.keyboard.press('Tab');
    keyboard.focusMoved = await keyboardPage.evaluate(() => document.activeElement !== document.body);
    for (let i = 0; i < 8; i += 1) {
      keyboard.tabSequence.push(await keyboardPage.evaluate(() => ({ tag: document.activeElement?.tagName || '', text: (document.activeElement?.textContent || document.activeElement?.getAttribute?.('aria-label') || '').trim().slice(0, 80) })));
      await keyboardPage.keyboard.press('Tab');
    }
    await keyboardPage.keyboard.press('Escape');
    await keyboardPage.waitForTimeout(500);
    keyboard.escapeCloses = await keyboardPage.locator('[role="dialog"]').count().then((count) => count === 0);
  } catch (error) {
    keyboard.error = String(error?.message || error);
  }
  await keyboardContext.close();

  const reduceContext = await browser.newContext({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
  const reducePage = await reduceContext.newPage();
  const reducedMotion = { route: '/', matched: false, screenshot: '0390-dashboard-reduced-motion.png' };
  try {
    await reducePage.goto(baseURL + '/', { waitUntil: 'domcontentloaded' });
    await waitForApp(reducePage);
    reducedMotion.matched = await reducePage.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
    await reducePage.screenshot({ path: path.join(outDir, reducedMotion.screenshot), fullPage: true });
  } catch (error) {
    reducedMotion.error = String(error?.message || error);
  }
  await reduceContext.close();

  const vitalsContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const vitalsPage = await vitalsContext.newPage();
  for (const [name, routePath] of routes) {
    try { vitals.push({ name, route: routePath, ...(await collectVitals(vitalsPage, routePath)) }); }
    catch (error) { vitals.push({ name, route: routePath, error: String(error?.message || error) }); }
  }
  await vitalsContext.close();
  await browser.close();
  await fs.writeFile(path.join(outDir, 'qa-matrix-results.json'), JSON.stringify({ generatedAt: new Date().toISOString(), baseURL, viewports, routes: routes.map(([name, route]) => ({ name, route })), screenshots, routeResults, axeResults, keyboard, reducedMotion, vitals }, null, 2));
}

main().catch((error) => { console.error(error); process.exit(1); });
