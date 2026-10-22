import { expect, test } from '@playwright/test'
import { installSyntheticApi } from './issue828Browser'

const category = 'Synthetic shared artwork'
const chapters = [
  { id: 1, title: 'Synthetic opener [Not provenance]', category_name: category, start: 0, end: 2 },
  { id: 2, title: 'Synthetic followup', category_name: category, start: 2, end: 4 },
  { id: 3, title: 'Synthetic unknown', category_name: 'Synthetic unknown artwork', start: 4, end: 6 },
  { id: 4, title: 'Synthetic offline', category_name: 'Synthetic offline artwork', start: 6, end: 8 },
  { id: 5, title: 'Synthetic title [No metadata]', category_name: null, start: 8, end: 12 },
]
const imagePath = '/api/media/categories/synthetic-artwork.svg'

for (const width of [320, 390, 863, 1440]) {
  for (const theme of ['dark', 'light'] as const) {
    for (const brokenImage of [false, true]) {
      test(`explicit cached chapter artwork ${width} ${theme} broken=${brokenImage}`, async ({ page }, testInfo) => {
        await page.setViewportSize({ width, height: 900 })
        await page.emulateMedia({ colorScheme: theme })
        const api = await installSyntheticApi(page, 'default')
        const calls: string[] = []
        const errors: string[] = []
        page.on('pageerror', error => errors.push(error.message))
        await page.route('**/api/videos/*/chapters', route => route.fulfill({ json: chapters }))
        await page.route('**/api/categories/image/*', route => {
          const request = route.request()
          if (request.method() !== 'GET') throw new Error('Unexpected category write')
          const name = decodeURIComponent(new URL(request.url()).pathname.split('/').pop()!)
          calls.push(name)
          if (name === category) return route.fulfill({ json: { category_name: name, image_url: imagePath } })
          if (name === 'Synthetic unknown artwork') return route.fulfill({ json: { category_name: name, image_url: null } })
          if (name === 'Synthetic offline artwork') return route.fulfill({ status: 503, json: { detail: 'Synthetic offline' } })
          throw new Error(`Unspecified category: ${name}`)
        })
        await page.route(`**${imagePath}`, route => brokenImage
          ? route.fulfill({ status: 404, body: 'Synthetic missing image' })
          : route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="128"><rect width="96" height="128" fill="navy"/><circle cx="48" cy="48" r="24" fill="gold"/></svg>' }))
        await page.goto('/videos/1')
        await expect.poll(() => page.locator('html').getAttribute('data-theme')).toBe(theme === 'light' ? 'light' : null)
        const video = page.locator('video.video-element')
        await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(2)
        const rows = page.locator('.chapter-item')
        await expect(rows).toHaveCount(5)
        await rows.first().scrollIntoViewIfNeeded()
        await expect.poll(() => calls.length).toBe(3)
        expect([...calls].sort()).toEqual([category, 'Synthetic unknown artwork', 'Synthetic offline artwork'].sort())
        if (brokenImage) {
          await expect(rows.locator('img')).toHaveCount(0)
          await expect(rows.first().locator('.chapter-artwork use')).toHaveAttribute('href', '#icon-gamepad')
        } else {
          await expect(rows.locator('img')).toHaveCount(2)
          await expect(rows.first().locator('img')).toHaveAttribute('src', imagePath)
          await expect.poll(() => rows.first().locator('img').evaluate(element => (element as HTMLImageElement).naturalWidth)).toBe(96)
          const artwork = (await rows.first().locator('.chapter-artwork').boundingBox())!
          expect(artwork.width).toBeGreaterThan(20)
          expect(artwork.width).toBeLessThanOrEqual(40)
        }
        for (const index of [2, 3, 4]) {
          await expect(rows.nth(index).locator('img')).toHaveCount(0)
          await expect(rows.nth(index).locator('.chapter-artwork use')).toHaveAttribute('href', '#icon-gamepad')
        }
        const geometry = await rows.evaluateAll(elements => elements.map(element => {
          const row = element.getBoundingClientRect()
          const text = element.querySelector('.chapter-details')!.getBoundingClientRect()
          return { top: row.top, bottom: row.bottom, textBottom: text.bottom }
        }))
        for (let index = 0; index < geometry.length; index++) {
          expect(geometry[index].textBottom, `chapter ${index + 1} keeps all metadata inside its row`).toBeLessThanOrEqual(geometry[index].bottom + 1)
          if (index) expect(geometry[index].top).toBeGreaterThanOrEqual(geometry[index - 1].bottom - 1)
        }
        await rows.nth(1).click()
        await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(2)
        await expect(rows.nth(1)).toHaveAttribute('aria-current', 'true')
        await rows.nth(4).click()
        await expect(rows.nth(4)).toHaveAttribute('aria-current', 'true')
        expect(calls).toHaveLength(3)
        expect(api.unexpected).toEqual([])
        expect(errors).toEqual([])
        await page.screenshot({ path: testInfo.outputPath('chapter-artwork.png') })
      })
    }
  }
}
