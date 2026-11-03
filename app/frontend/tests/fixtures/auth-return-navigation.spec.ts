import { expect, test, type Page } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
import { syntheticReply } from './issue828SyntheticApi'

for (const warm of [false, true]) {
  for (const late401 of [false, true]) {
    test(`login retains draft and return path warm=${warm} late401=${late401}`, async ({ context, page: initialPage }, testInfo) => {
      let page: Page = initialPage
      let authenticated = false
      let holding = false
      let release!: () => void
      const gate = new Promise<void>(resolve => { release = resolve })
      let held = 0
      let delivered = 0
      let refreshes = 0
      const unexpected: string[] = []
      await context.routeWebSocket(/.*/, socket => socket.close())
      await context.route('**/*', async route => {
        const request = route.request()
        const url = new URL(request.url())
        if (url.origin !== 'http://127.0.0.1:4190') {
          unexpected.push(`external ${url.origin}${url.pathname}`)
          return route.abort('blockedbyclient')
        }
        if (request.isNavigationRequest() || !/^\/(api|auth)\//.test(url.pathname)) return route.continue()
        if (url.pathname === '/auth/setup') return route.fulfill({ json: { setup_required: false, welcome_completed: true } })
        if (url.pathname === '/auth/check') return route.fulfill({ json: { authenticated } })
        if (url.pathname === '/auth/refresh') {
          refreshes++
          return route.fulfill({ status: 401, json: { detail: 'Synthetic expired session' } })
        }
        if (url.pathname === '/auth/login' && request.method() === 'POST') {
          authenticated = true
          return route.fulfill({ json: { success: true } })
        }
        if (url.pathname === '/auth/keepalive') return route.fulfill({ json: { success: authenticated } })
        if (holding && !authenticated && url.pathname.startsWith('/api/')) {
          held++
          await gate
          delivered++
          return route.fulfill({ status: 401, json: { detail: 'Synthetic expired session' } })
        }
        const reply = syntheticReply(url.pathname + url.search, request.method())
        if (reply.status !== 200) unexpected.push(`${request.method()} ${url.pathname}`)
        return route.fulfill({ status: reply.status, json: reply.body })
      })
      if (warm) {
        await page.goto('/auth/login')
        await expect(page.getByLabel('Username', { exact: true })).toBeVisible()
        await page.evaluate(async () => { await navigator.serviceWorker.ready })
        await page.close()
        page = await context.newPage()
      }
      holding = late401
      const navigationRequests: string[] = []
      const documents: string[] = []
      const frameLocations: string[] = []
      page.on('request', request => { if (request.isNavigationRequest() && request.frame() === page.mainFrame()) navigationRequests.push(request.url()) })
      page.on('domcontentloaded', () => documents.push(page.url()))
      page.on('framenavigated', frame => { if (frame === page.mainFrame()) frameLocations.push(frame.url()) })
      await page.goto('/streamers?probe=synthetic')
      const username = page.getByLabel('Username', { exact: true })
      await expect(username).toBeVisible()
      const input = (await username.elementHandle())!
      await username.fill('synthetic-unsaved-name')
      const renderedUrl = page.url()
      const renderedDocuments = documents.length
      release()
      if (late401) {
        await expect.poll(() => held).toBeGreaterThan(1)
        await expect.poll(() => delivered).toBe(held)
      }
      await page.evaluate(async () => { await navigator.serviceWorker.ready })
      // Explicit observation window for startup activation and late auth responses.
      await page.waitForTimeout(1500)
      const beforeSubmit = {
        renderedUrl, url: page.url(), renderedDocuments, documents: [...documents],
        navigationRequests: [...navigationRequests], frameLocations: [...frameLocations],
        held, delivered, refreshes, inputStillConnected: await input.evaluate(node => node.isConnected),
        username: await username.inputValue(), serviceWorkers: context.serviceWorkers().length,
        navigationEntries: await page.evaluate(() => performance.getEntriesByType('navigation').map(entry => ({
          name: entry.name, type: (entry as PerformanceNavigationTiming).type,
        }))),
      }
      await writeFile(testInfo.outputPath('startup-observation.json'), JSON.stringify(beforeSubmit, null, 2))
      expect(beforeSubmit.navigationRequests).toHaveLength(1)
      expect(beforeSubmit.navigationEntries).toHaveLength(1)
      expect(beforeSubmit.navigationEntries[0].type).toBe('navigate')
      expect(beforeSubmit.refreshes).toBe(late401 ? 1 : 0)
      expect(new URL(beforeSubmit.url).searchParams.get('returnTo')).toBe('/streamers?probe=synthetic')
      expect(beforeSubmit.documents.length, 'no second document after login becomes visible').toBe(renderedDocuments)
      expect(beforeSubmit.inputStillConnected, 'startup must not remount the form').toBe(true)
      await expect(username).toHaveValue('synthetic-unsaved-name')
      await page.getByLabel('Password', { exact: true }).fill('synthetic-only-not-a-credential')
      await page.getByRole('button', { name: 'Sign In', exact: true }).click()
      await expect(page).toHaveURL('http://127.0.0.1:4190/streamers?probe=synthetic')
      expect(unexpected).toEqual([])
    })
  }
}
