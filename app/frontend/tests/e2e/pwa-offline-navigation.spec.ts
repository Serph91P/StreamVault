import { expect, test } from '@playwright/test'

test('active service worker serves the app shell for offline /streamers navigation', async ({ page, context }) => {
  await page.goto('/')
  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready
    await registration.active?.postMessage({ type: 'SKIP_WAITING' })
  })
  await page.reload()

  const serviceWorkerState = await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready
    const cacheNames = await caches.keys()
    const cacheEntries = await Promise.all(cacheNames.map(async (cacheName) => {
      const cache = await caches.open(cacheName)
      return (await cache.keys()).map((request) => new URL(request.url).pathname)
    }))

    return {
      scope: registration.scope,
      activeScript: registration.active?.scriptURL,
      controllerScript: navigator.serviceWorker.controller?.scriptURL,
      cacheNames,
      cachedPaths: cacheEntries.flat(),
    }
  })

  console.info('pwa-service-worker-state', JSON.stringify(serviceWorkerState))

  expect(serviceWorkerState.scope).toBe(new URL('/', page.url()).href)
  expect(serviceWorkerState.activeScript).toContain('/sw.js')
  expect(serviceWorkerState.controllerScript).toContain('/sw.js')
  expect(serviceWorkerState.cacheNames).toEqual(expect.arrayContaining([
    expect.stringContaining('workbox-precache'),
  ]))
  expect(serviceWorkerState.cachedPaths).toEqual(expect.arrayContaining([
    '/android-icon-192x192.png',
    '/icon-512x512.png',
    '/maskable-icon-192x192.png',
    '/maskable-icon-512x512.png',
  ]))

  await context.setOffline(true)
  await expect.poll(() => page.evaluate(() => navigator.onLine)).toBe(false)
  await page.goto('/streamers')
  await expect(page.locator('#app')).not.toBeEmpty()

  await context.setOffline(false)
  await expect.poll(() => page.evaluate(() => navigator.onLine)).toBe(true)
  await page.reload()
  await expect(page.locator('#app')).not.toBeEmpty()
})
