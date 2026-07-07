const { chromium } = require('playwright')
const fs = require('node:fs')
const path = require('node:path')

const baseUrl = process.env.ADMIN_QA_BASE_URL || 'http://127.0.0.1:5173'
const outDir = path.resolve(__dirname)

const rawDiagnosticLabels = [
  'Test Apprise Notification',
  'Test Web Push Notification',
  'Test WebSocket Notification',
  'Run All Tests',
  'Show Available Tests',
  'Fix Recording Paths',
  'Cleanup Orphaned DB',
  'Cleanup Process Orphaned',
  'Cleanup Zombie Recordings',
]

async function visibleText(page, text) {
  return await page.getByText(text, { exact: true }).first().isVisible().catch(() => false)
}

async function collectMetrics(page) {
  return await page.evaluate(() => ({
    url: location.pathname,
    bodyText: document.body.innerText,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    primaryButtons: Array.from(document.querySelectorAll('button.btn-primary'))
      .filter(button => {
        const style = window.getComputedStyle(button)
        if (style.display === 'none' || style.visibility === 'hidden' || button.getClientRects().length === 0) return false
        const closedDetails = button.closest('details:not([open])')
        return !closedDetails || Boolean(button.closest('summary'))
      })
      .map(button => button.textContent?.trim().replace(/\s+/g, ' ')),
    visibleSummaries: Array.from(document.querySelectorAll('details.admin-disclosure > summary')).map(summary => summary.textContent?.trim().replace(/\s+/g, ' ')),
  }))
}

async function runViewport(browser, name, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, reducedMotion: 'reduce' })
  const page = await context.newPage()
  const consoleMessages = []
  const pageErrors = []

  page.on('console', msg => consoleMessages.push({ type: msg.type(), text: msg.text() }))
  page.on('pageerror', err => pageErrors.push(err.message))

  await page.route('**/admin/websocket-connections', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_connections: 2,
        unique_clients: 2,
        clients: [
          { ip: '127.0.0.1', count: 1, connections: [{ connection_id: 1, real_ip: '127.0.0.1', client_identifier: 'mock-admin', state: 'Connected' }] },
          { ip: '192.0.2.10', count: 1, connections: [{ connection_id: 2, real_ip: '192.0.2.10', client_identifier: 'mock-mobile', state: 'Connected' }] },
        ],
        connections: [],
      }),
    })
  })

  await page.goto(`${baseUrl}/admin`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.admin-panel', { timeout: 15000 })

  const initialShot = path.join(outDir, `admin-${name}-initial.png`)
  await page.screenshot({ path: initialShot, fullPage: true })

  const rawVisibilityBefore = {}
  for (const label of rawDiagnosticLabels) {
    rawVisibilityBefore[label] = await visibleText(page, label)
  }

  const initialMetrics = await collectMetrics(page)

  const disclosureCount = await page.locator('details.admin-disclosure').count()
  const notificationDetails = page.locator('details.admin-disclosure').filter({ hasText: 'Notification Diagnostics' }).first()
  await notificationDetails.locator('summary').click()
  await page.waitForTimeout(250)
  const openedShot = path.join(outDir, `admin-${name}-notification-diagnostics-open.png`)
  await page.screenshot({ path: openedShot, fullPage: true })

  const rawVisibilityAfter = {}
  for (const label of rawDiagnosticLabels.slice(0, 3)) {
    rawVisibilityAfter[label] = await visibleText(page, label)
  }

  const openedMetrics = await collectMetrics(page)

  await context.close()
  return {
    name,
    viewport,
    screenshots: { initial: initialShot, notificationDiagnosticsOpen: openedShot },
    disclosureCount,
    rawVisibilityBefore,
    rawVisibilityAfter,
    metrics: {
      initial: {
        url: initialMetrics.url,
        viewportWidth: initialMetrics.viewportWidth,
        viewportHeight: initialMetrics.viewportHeight,
        scrollWidth: initialMetrics.scrollWidth,
        clientWidth: initialMetrics.clientWidth,
        hasHorizontalOverflow: initialMetrics.hasHorizontalOverflow,
        primaryButtons: initialMetrics.primaryButtons,
        visibleSummaries: initialMetrics.visibleSummaries,
        containsAdminHeader: initialMetrics.bodyText.includes('Admin'),
        containsSystemHealth: initialMetrics.bodyText.includes('System Health'),
        containsBackgroundJobs: initialMetrics.bodyText.includes('Background Jobs & Services'),
      },
      afterNotificationDisclosureOpen: {
        primaryButtons: openedMetrics.primaryButtons,
        hasHorizontalOverflow: openedMetrics.hasHorizontalOverflow,
      },
    },
    consoleMessages,
    pageErrors,
  }
}

;(async () => {
  const browser = await chromium.launch({ headless: true })
  const results = []
  try {
    results.push(await runViewport(browser, 'desktop', { width: 1440, height: 1000 }))
    results.push(await runViewport(browser, 'mobile', { width: 390, height: 844 }))
  } finally {
    await browser.close()
  }

  const failures = []
  for (const result of results) {
    if (result.disclosureCount < 5) failures.push(`${result.name}: expected diagnostic/admin tools to be grouped behind disclosures`)
    if (result.metrics.initial.hasHorizontalOverflow) failures.push(`${result.name}: page has horizontal overflow ${result.metrics.initial.scrollWidth}/${result.metrics.initial.clientWidth}`)
    if (!result.metrics.initial.containsAdminHeader || !result.metrics.initial.containsSystemHealth || !result.metrics.initial.containsBackgroundJobs) {
      failures.push(`${result.name}: core admin sections missing from rendered page`)
    }
    for (const [label, visible] of Object.entries(result.rawVisibilityBefore)) {
      if (visible) failures.push(`${result.name}: raw diagnostic action visible before disclosure: ${label}`)
    }
    for (const [label, visible] of Object.entries(result.rawVisibilityAfter)) {
      if (!visible) failures.push(`${result.name}: notification diagnostic action not visible after opening disclosure: ${label}`)
    }
    if (result.pageErrors.length > 0) failures.push(`${result.name}: page errors: ${result.pageErrors.join('; ')}`)
  }

  const report = {
    baseUrl,
    generatedAt: new Date().toISOString(),
    pass: failures.length === 0,
    failures,
    results,
  }
  const reportPath = path.join(outDir, 'admin-visual-qa-report.json')
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
  console.log(JSON.stringify({ pass: report.pass, failures, reportPath, screenshots: results.map(result => result.screenshots) }, null, 2))
  if (failures.length > 0) process.exit(1)
})().catch(error => {
  console.error(error)
  process.exit(1)
})
