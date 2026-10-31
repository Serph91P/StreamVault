import { expect, test, type Page } from '@playwright/test'
import { installSyntheticApi } from './issue828Browser'
import type { App } from 'vue'

// Exercise the app's installed router (the same path used by notifications),
// not history.pushState or a document navigation.
async function push(page: Page, path: string) {
  await page.evaluate(path => (document.querySelector('#app') as Element & { __vue_app__: App }).__vue_app__.config.globalProperties.$router.push(path), path)
}
async function recording(page: Page, id: number) {
  await expect(page.locator('.video-title')).toHaveText(`Synthetic alpha recording 0${id}`)
  await expect(page.locator('video')).toHaveAttribute('src', `/api/videos/${id}/stream`)
  await expect(page.locator('.info-row').filter({ hasText: 'Stream ID' })).toContainText(`#${id}`)
  await expect(page.locator('.chapters-list')).toContainText(`Recording ${id} chapter`)
  await expect(page.getByRole('button', { name: 'Share', exact: true })).toBeEnabled()
}

for (const route of [(id: number) => `/videos/${id}`, (id: number) => `/streamer/1/stream/${id}/watch`]) {
  test(`route reuse and Back/Forward preserve identity: ${route(1)}`, async ({ page }) => {
    const api = await installSyntheticApi(page, 'one'); api.releaseChapters()
    await page.route('**/api/videos/*/chapters', route => {
      const id = Number(route.request().url().match(/videos\/(\d+)/)![1])
      return route.fulfill({ json: [{ id, title: `Recording ${id} chapter`, start: 0, end: 12 }] })
    })
    const documents: string[] = []
    page.on('request', request => { if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents.push(request.url()) })
    await page.goto(route(1))
    await recording(page, 1)
    const oldVideo = await page.locator('video').elementHandle()
    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await push(page, route(2))
    await recording(page, 2)
    await expect(page.getByRole('dialog')).toHaveCount(0)
    expect(await oldVideo!.evaluate(video => video.isConnected)).toBe(false)
    await page.goBack(); await recording(page, 1)
    await page.goForward(); await recording(page, 2)
    await push(page, '/streamer/1/stream/1/watch'); await recording(page, 1)
    await push(page, '/videos/2'); await recording(page, 2)
    expect(documents).toHaveLength(1)
    expect(api.unexpected).toEqual([])
  })
}

test('Slow1/Fast2 and repeated reversals ignore obsolete chapters', async ({ page }) => {
  const api = await installSyntheticApi(page, 'one'); api.releaseChapters()
  let release!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  let first = true
  await page.route('**/api/videos/*/chapters', async route => {
    const id = Number(route.request().url().match(/videos\/(\d+)/)![1])
    if (id === 1 && first) { first = false; await held }
    await route.fulfill({ json: [{ id, title: `Recording ${id} chapter`, start: 0, end: 12 }] })
  })
  await page.goto('/videos/1')
  await expect.poll(() => first).toBe(false)
  await push(page, '/videos/2'); await recording(page, 2)
  await push(page, '/videos/1'); await recording(page, 1)
  await push(page, '/videos/2'); await recording(page, 2)
  const obsoleteResponse = page.waitForResponse(response => response.url().endsWith('/api/videos/1/chapters'))
  release()
  await (await obsoleteResponse).finished()
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  await expect.poll(() => page.locator('.video-title').textContent()).toBe('Synthetic alpha recording 02')
  await recording(page, 2)
  expect(api.unexpected).toEqual([])
})

test('replacement loading hides old media/actions and cannot confirm the old delete dialog', async ({ page }) => {
  const api = await installSyntheticApi(page, 'one'); api.releaseChapters()
  let release!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/videos/*/chapters', async route => {
    const id = Number(route.request().url().match(/videos\/(\d+)/)![1])
    if (id === 2) await held
    await route.fulfill({ json: [{ id, title: `Recording ${id} chapter`, start: 0, end: 12 }] })
  })
  await page.goto('/videos/1'); await recording(page, 1)
  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await push(page, '/videos/2')
  await expect(page.locator('video')).toHaveCount(0)
  await expect(page.locator('.action-btn')).toHaveCount(0)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(api.requests.filter(path => /share|delete/.test(path))).toEqual([])
  release(); await recording(page, 2)
})
