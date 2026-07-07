const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const appUrl = process.env.APP_URL || 'http://127.0.0.1:5173/'
const evidenceDir = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/.hermes/frontend-visual-evidence/notification-center'
fs.mkdirSync(evidenceDir, { recursive: true })

function notificationsFixture() {
  const base = Date.now()
  const iso = (msAgo) => new Date(base - msAgo).toISOString()
  return [
    {
      id: 'evt-live-1',
      event_id: 'evt-live-1',
      dedupe_key: 'stream:alice:online',
      type: 'stream.online',
      severity: 'info',
      title: 'Alice is Live',
      body: 'Alice is live: Deep Space Speedruns',
      timestamp: iso(2 * 60 * 1000),
      created_at: iso(2 * 60 * 1000),
      source: 'websocket',
      target_url: '/streamers/101',
      streamer_id: 101,
      streamer_username: 'alice',
      streamer_name: 'Alice',
      actions: [{ id: 'open', label: 'Open', target_url: '/streamers/101' }],
      data: { game_name: 'Starfield' },
      read: false
    },
    {
      id: 'evt-rec-1',
      event_id: 'evt-rec-1',
      dedupe_key: 'recording:alice:42',
      type: 'recording.completed',
      severity: 'success',
      title: 'Recording Completed',
      body: 'Successfully completed recording Alice stream',
      timestamp: iso(70 * 60 * 1000),
      created_at: iso(70 * 60 * 1000),
      source: 'push',
      target_url: '/videos/42',
      streamer_id: 101,
      streamer_username: 'alice',
      streamer_name: 'Alice',
      recording_id: 42,
      video_id: 42,
      actions: [{ id: 'open', label: 'Open', target_url: '/videos/42' }],
      data: { category_name: 'Science and Technology' },
      read: true,
      read_at: iso(60 * 60 * 1000)
    },
    {
      id: 'evt-fail-1',
      event_id: 'evt-fail-1',
      dedupe_key: 'recording:bob:fail',
      type: 'recording.failed',
      severity: 'critical',
      title: 'Recording Failed',
      body: 'Recording failed for Bob: Disk full',
      timestamp: iso(26 * 60 * 60 * 1000),
      created_at: iso(26 * 60 * 60 * 1000),
      source: 'apprise',
      target_url: '/settings#notifications',
      streamer_id: 202,
      streamer_username: 'bob',
      streamer_name: 'Bob',
      actions: [{ id: 'open', label: 'Open', target_url: '/settings#notifications' }],
      data: { error_message: 'Disk full' },
      read: false
    },
    {
      id: 'evt-system-1',
      event_id: 'evt-system-1',
      dedupe_key: 'system:queue:warn',
      type: 'task_status_update',
      severity: 'warning',
      title: 'Queue Warning',
      body: 'Background worker retry threshold reached',
      timestamp: iso(3 * 24 * 60 * 60 * 1000),
      created_at: iso(3 * 24 * 60 * 60 * 1000),
      source: 'system',
      target_url: '',
      actions: [],
      data: {},
      read: false
    }
  ]
}

async function seedContext(context) {
  await context.addInitScript((items) => {
    window.localStorage.setItem('streamvault_notifications', JSON.stringify(items))
  }, notificationsFixture())
}

async function waitForApp(page) {
  await page.goto(appUrl, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: /Open notifications/ }).waitFor({ timeout: 15000 })
}

async function openCenter(page) {
  await page.getByRole('button', { name: /Open notifications/ }).click()
  await page.getByRole('dialog', { name: 'Notifications' }).waitFor({ timeout: 10000 })
  await page.locator('.notification-item').first().waitFor({ timeout: 10000 })
}

async function countItems(page) {
  return await page.locator('.notification-item').evaluateAll((items) => {
    return items.filter((item) => {
      const rect = item.getBoundingClientRect()
      const style = window.getComputedStyle(item)
      return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none'
    }).length
  })
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 })
  await seedContext(desktopContext)
  const page = await desktopContext.newPage()
  const consoleMessages = []
  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) consoleMessages.push(`${msg.type()}: ${msg.text()}`)
  })

  await waitForApp(page)
  await openCenter(page)
  await page.screenshot({ path: path.join(evidenceDir, 'desktop-notification-center.png'), fullPage: true })

  const initial = {
    totalText: await page.getByText('3 unread of 4 notifications').count(),
    items: await countItems(page),
    today: await page.getByText('Today').count(),
    yesterday: await page.getByText('Yesterday').count(),
    olderGroup: await page.locator('.notification-group').filter({ hasText: 'Queue Warning' }).locator('.notification-group-header h3').textContent(),
    websocket: await page.getByText('WebSocket').count(),
    pushDelivery: await page.getByText('Push delivery').count(),
    appriseDelivery: await page.getByText('Apprise delivery').count(),
    systemEvent: await page.getByText('System event').count(),
    targetStreamer: await page.getByText('Target: /streamers/101').count(),
    targetVideo: await page.getByText('Target: /videos/42').count(),
    targetSettings: await page.getByText('Target: /settings#notifications').count()
  }
  if (initial.totalText !== 2 || initial.items !== 4) throw new Error(`initial notification count failed: ${JSON.stringify(initial)}`)
  if (!initial.today || !initial.yesterday || !initial.olderGroup) throw new Error(`group labels missing: ${JSON.stringify(initial)}`)
  if (!initial.websocket || !initial.pushDelivery || !initial.appriseDelivery || !initial.systemEvent) throw new Error(`delivery labels missing: ${JSON.stringify(initial)}`)
  if (!initial.targetStreamer || !initial.targetVideo || !initial.targetSettings) throw new Error(`target labels missing: ${JSON.stringify(initial)}`)

  await page.locator('.notification-filters .unread-chip').click()
  await page.waitForTimeout(500)
  const unreadItems = await countItems(page)
  if (unreadItems !== 3) throw new Error(`unread filter expected 3 items, saw ${unreadItems}`)

  await page.locator('.notification-filters .source-chip').filter({ hasText: 'Push' }).click()
  await page.waitForTimeout(500)
  const pushItems = await countItems(page)
  if (pushItems !== 1 || !(await page.getByText('Recording Completed').count())) throw new Error(`push filter failed, saw ${pushItems}`)

  await page.locator('.notification-filters .primary-filters .filter-chip').first().click()
  await page.waitForTimeout(500)
  await page.locator('.notification-item').filter({ hasText: 'Alice is Live' }).getByRole('button', { name: /read/i }).click()
  await page.waitForTimeout(150)
  const unreadAfterRead = await page.getByText('2 unread of 4 notifications').count()
  if (unreadAfterRead !== 2) throw new Error('mark single notification read did not update count')

  await page.locator('.notification-item').filter({ hasText: 'Alice is Live' }).getByRole('button', { name: /unread/i }).click()
  await page.waitForTimeout(150)
  const unreadAfterUnread = await page.getByText('3 unread of 4 notifications').count()
  if (unreadAfterUnread !== 2) throw new Error('mark single notification unread did not restore count')

  const realtimeResult = await page.evaluate(async () => {
    const [{ useNotificationStore }, { toCanonicalNotificationEvent }] = await Promise.all([
      import('/src/stores/notifications.ts'),
      import('/src/types/events.ts')
    ])
    const store = useNotificationStore()
    const duplicate = toCanonicalNotificationEvent({
      type: 'stream.online',
      data: {
        event_id: 'evt-live-1',
        dedupe_key: 'stream:alice:online',
        streamer_id: 101,
        streamer_name: 'Alice',
        stream_title: 'Deep Space Speedruns Updated',
        timestamp: new Date().toISOString()
      }
    })
    const apprise = toCanonicalNotificationEvent({
      type: 'notification_event',
      data: {
        event_id: 'evt-apprise-2',
        dedupe_key: 'apprise:test:2',
        type: 'test',
        title: 'Apprise Test Delivered',
        body: 'External Apprise path delivered while in-app remains live',
        source: 'apprise',
        created_at: new Date().toISOString(),
        target_url: '/settings#notifications'
      }
    })
    store.addFromEvent(duplicate)
    store.addFromEvent(duplicate)
    store.addFromEvent(apprise)
    return {
      total: store.totalCount,
      unread: store.unreadCount,
      aliceCount: store.notifications.filter((n) => n.event_id === 'evt-live-1').length,
      appriseCount: store.notifications.filter((n) => n.event_id === 'evt-apprise-2').length
    }
  })
  if (realtimeResult.total !== 5 || realtimeResult.aliceCount !== 1 || realtimeResult.appriseCount !== 1) {
    throw new Error(`realtime dedupe simulation failed: ${JSON.stringify(realtimeResult)}`)
  }
  await page.waitForTimeout(200)
  const appriseVisible = await page.getByText('Apprise Test Delivered').count()
  if (appriseVisible !== 1) throw new Error('simulated realtime Apprise item not visible')

  await page.getByRole('button', { name: /Open notification target for Alice is Live/ }).click()
  await page.waitForURL('**/streamers/101', { timeout: 10000 })
  const targetUrl = page.url()
  if (!targetUrl.endsWith('/streamers/101')) throw new Error(`target navigation failed: ${targetUrl}`)

  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 2 })
  await seedContext(mobileContext)
  const mobilePage = await mobileContext.newPage()
  await waitForApp(mobilePage)
  await openCenter(mobilePage)
  await mobilePage.screenshot({ path: path.join(evidenceDir, 'mobile-notification-center.png'), fullPage: true })
  const mobile = {
    dialog: await mobilePage.getByRole('dialog', { name: 'Notifications' }).count(),
    items: await mobilePage.locator('.notification-item').count(),
    filters: await mobilePage.locator('.notification-filters').count(),
    panelBox: await mobilePage.locator('#notification-panel').boundingBox()
  }
  if (mobile.dialog !== 1 || mobile.items !== 4 || mobile.filters !== 1) throw new Error(`mobile notification sheet failed: ${JSON.stringify(mobile)}`)

  await browser.close()

  const result = {
    initial,
    unreadItems,
    pushItems,
    realtimeResult,
    targetUrl,
    mobile,
    consoleMessages,
    screenshots: [
      path.join(evidenceDir, 'desktop-notification-center.png'),
      path.join(evidenceDir, 'mobile-notification-center.png')
    ]
  }
  fs.writeFileSync(path.join(evidenceDir, 'verification-result.json'), JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
