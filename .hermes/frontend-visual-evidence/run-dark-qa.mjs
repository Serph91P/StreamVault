import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

const frontendDir = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/app/frontend';
const require = createRequire(path.join(frontendDir, 'package.json'));
const { chromium } = require('playwright');
const baseURL = 'http://127.0.0.1:5173';
const outDir = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/.hermes/frontend-visual-evidence';
const viewports = [390, 430, 768, 1440];
const routes = [['dashboard','/'], ['settings','/settings'], ['library','/videos']];

await fs.mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const results = [];
for (const width of viewports) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: 'dark' });
  await context.addInitScript(() => localStorage.setItem('streamvault-theme', 'dark'));
  const page = await context.newPage();
  for (const [name, route] of routes) {
    const row = { width, name, route };
    try {
      await page.goto(baseURL + route, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => null);
      await page.locator('#app').waitFor({ timeout: 20000 });
      await page.waitForTimeout(350);
      const file = `dark-${String(width).padStart(4, '0')}-${name}.png`;
      await page.screenshot({ path: path.join(outDir, file), fullPage: true });
      Object.assign(row, await page.evaluate(() => ({
        ok: true,
        htmlTheme: document.documentElement.getAttribute('data-theme') || 'dark-default',
        toggleLabel: document.querySelector('[aria-label^="Switch to"]')?.getAttribute('aria-label') || null,
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        bodyTextStart: document.body.innerText.replace(/\s+/g, ' ').trim().slice(0, 160),
      })));
      row.screenshot = file;
    } catch (error) {
      row.ok = false;
      row.error = String(error?.message || error);
    }
    results.push(row);
  }
  await context.close();
}
await browser.close();
await fs.writeFile(path.join(outDir, 'dark-qa-results.json'), JSON.stringify({ generatedAt: new Date().toISOString(), viewports, routes: routes.map(([name, route]) => ({ name, route })), results }, null, 2));
console.log(JSON.stringify({ ok: results.filter(r => r.ok).length, total: results.length, overflow: results.filter(r => r.horizontalOverflow) }, null, 2));
