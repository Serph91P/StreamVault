// Opt-in real Mozilla provider receipt; requires the companion disposable server.
// Run from repository root: node tests/manual/webpush_provider.cjs
// Linux: Firefox needs an X display (e.g. Xvfb) for native notification display.
const { firefox } = require('../../app/frontend/node_modules/playwright');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const profile = mkdtempSync(join(tmpdir(), 'webpush-firefox-'));
  let context;
  try {
    context = await firefox.launchPersistentContext(profile, {
      headless: false,
      permissions: ['notifications'],
      firefoxUserPrefs: {
        'alerts.useSystemBackend': false,
        'dom.push.enabled': true,
        'dom.push.connection.enabled': true,
        'dom.push.serverURL': 'wss://push.services.mozilla.com/',
        'dom.webnotifications.enabled': true,
        'dom.webnotifications.serviceworker.enabled': true,
      },
    });
    const page = await context.newPage();
    await page.goto('http://127.0.0.1:4187/probe.html');
    // Fail at the actual HTTP boundary if a generated precache URL is unavailable.
    const sw = await (await page.request.get('http://127.0.0.1:4187/sw.js')).text();
    const urls = [...sw.matchAll(/\{url:"([^"]+)",revision:/g)].map(match => match[1]);
    assert.ok(urls.length > 0, 'Generated precache manifest must be present');
    for (const url of urls) {
      const response = await page.request.get(new URL(url, page.url()).href);
      assert.equal(response.status(), 200, `Unreachable precache URL: ${url}`);
    }
    console.log('PRECACHE_HTTP', urls.length, 'PASS');
    let timer;
    try {
      const receipt = await Promise.race([
        page.evaluate(async () => {
          await navigator.serviceWorker.register('/sw.js');
          const reg = await navigator.serviceWorker.ready;
          const { publicKey } = await (await fetch('/api/push/vapid-public-key')).json();
          const key = Uint8Array.from(atob(publicKey.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
          const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
          const saved = await (await fetch('/api/push/subscribe', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subscription: sub.toJSON(), userAgent: 'synthetic-provider-probe' }),
          })).json();
          if (!saved.success) throw new Error('Subscription persistence failed');
          const result = await (await fetch('/api/push/test', { method: 'POST' })).json();
          return { providerHost: new URL(sub.endpoint).hostname, serviceWorker: reg.active.scriptURL, ...result };
        }),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Subscribe/send timed out')), 60000); }),
      ]);
      assert.equal(receipt.success, true);
      assert.equal(receipt.sent_count, 1);
      assert.equal(receipt.failed_count, 0);
      console.log('NATIVE_RECEIPT', JSON.stringify(receipt));
    } finally { clearTimeout(timer); }
    let display = [];
    const deadline = Date.now() + 60000;
    while (display.length === 0 && Date.now() < deadline) {
      display = await page.evaluate(async () => {
        const notes = await (await navigator.serviceWorker.ready).getNotifications();
        return notes.filter(n => n.title === '🧪 StreamVault Test').map(n => ({ title: n.title, body: n.body }));
      });
      if (!display.length) await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.equal(display.length, 1, 'Missing provider-delivered notification');
    assert.equal(display[0].body, 'This is a test notification from StreamVault. If you see this, push notifications are working!');
    console.log('NATIVE_DISPLAY', JSON.stringify(display));
  } finally {
    if (context) {
      for (const page of context.pages()) {
        await page.evaluate(async () => {
          const reg = await navigator.serviceWorker.getRegistration();
          if (!reg) return;
          (await reg.getNotifications()).forEach(n => n.close());
          const sub = await reg.pushManager.getSubscription();
          if (sub) await sub.unsubscribe();
          await reg.unregister();
        }).catch(() => {});
      }
      await context.close();
    }
    rmSync(profile, { recursive: true, force: true });
  }
})().catch(error => {
  console.error('PROBE_FAILED', error.message.replace(/https:\/\/[^\s]+/g, '[url-redacted]'));
  process.exitCode = 1;
});
