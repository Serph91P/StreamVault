import { expect, test } from '@playwright/test'
import { readdirSync } from 'node:fs'
import originals from './player-control-originals.json' with { type: 'json' }

test('external player glyphs render exactly like the original geometry in both themes', async ({ page }) => {
  await page.route('**/player-glyph-comparison', route => route.fulfill({
    contentType: 'text/html',
    body: '<!doctype html><style>body{margin:0}svg{display:block;width:24px;height:24px}</style><main></main>',
  }))
  await page.goto('/player-glyph-comparison')
  const files = readdirSync(new URL('../../dist/assets', import.meta.url))
    .filter(file => /^player-controls-[\w-]+\.svg$/.test(file))
  expect(files).toHaveLength(1)
  const asset = `/assets/${files[0]}`
  const response = await page.request.get(asset)
  expect(response.status()).toBe(200)
  expect(response.headers()['content-type']).toContain('image/svg+xml')
  for (const color of ['#191919', '#eeeeee']) {
    for (const glyph of originals) {
      await page.locator('main').evaluate((main, { glyph, color, asset }) => {
        const attributes = `viewBox="0 0 24 24" fill="${glyph.fill}" stroke="${glyph.stroke}" stroke-width="2"`
        main.style.color = color
        main.innerHTML = `<svg id="original" ${attributes}>${glyph.geometry}</svg><svg id="external" ${attributes}><use href="${asset}#${glyph.id}"/></svg>`
      }, { glyph, color, asset })
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
      const original = await page.locator('#original').screenshot()
      const external = await page.locator('#external').screenshot()
      expect(external.equals(original), `${glyph.id} ${color}`).toBe(true)
    }
  }
})
