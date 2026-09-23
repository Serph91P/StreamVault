import { expect, test } from '@playwright/test'

const canonicalManifestPath = '/manifest.webmanifest'

test('serves one valid canonical VitePWA manifest', async ({ page, request }) => {
  await page.goto('/')

  const manifestLinks = page.locator('link[rel="manifest"]')
  await expect(manifestLinks).toHaveCount(1)
  await expect(manifestLinks).toHaveAttribute('href', canonicalManifestPath)

  const response = await request.get(canonicalManifestPath)
  expect(response.ok()).toBe(true)
  expect(response.headers()['content-type']).toContain('application/manifest+json')

  const manifest = await response.json()
  expect(manifest).toMatchObject({
    name: 'StreamVault',
    short_name: 'StreamVault',
    start_url: '/?source=pwa',
    scope: '/',
    display: 'standalone',
  })
  expect(manifest.icons).toEqual(expect.arrayContaining([
    expect.objectContaining({ src: '/android-icon-192x192.png' }),
    expect.objectContaining({ src: '/maskable-icon-192x192.png', purpose: 'maskable' }),
  ]))
})
