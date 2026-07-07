const { chromium } = require('playwright')
const { execFileSync } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')

const base = 'http://localhost:7001'
const userDataDir = path.join(process.cwd(), '.hermes', 'browser-push-profile')

function createSession() {
  const raw = 'qa_' + crypto.randomBytes(32).toString('base64url')
  const hash = crypto.createHash('sha256').update(raw).digest('hex')
  const py = `
from app.database import SessionLocal
from app.models import User, Session
from datetime import datetime, timezone
import json
raw = ${JSON.stringify(raw)}
token_hash = ${JSON.stringify(hash)}
with SessionLocal() as db:
    user = db.query(User).filter_by(is_admin=True).first()
    db.add(Session(user_id=user.id, token=token_hash, created_at=datetime.now(timezone.utc)))
    db.commit()
    print(json.dumps({"user_id": user.id, "username": user.username, "token": raw}))
`
  const out = execFileSync('docker', ['exec', '-i', 'streamvault-develop', 'python', '-'], { input: py, encoding: 'utf8' })
  return JSON.parse(out.trim().split('\n').pop())
}

async function main() {
  fs.rmSync(userDataDir, { recursive: true, force: true })
  fs.mkdirSync(userDataDir, { recursive: true })
  const session = createSession()
  const result = {
    timestamp: new Date().toISOString(),
    base,
    session: { user_id: session.user_id, username: session.username },
    environment: {
      node: process.version,
      display: process.env.DISPLAY || null,
      playwrightBrowsersPath: process.env.PLAYWRIGHT_BROWSERS_PATH || null,
      headless: process.env.HEADFUL ? false : true,
      persistentProfile: userDataDir,
    },
    steps: [],
    gates: {},
  }

  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: !process.env.HEADFUL,
    baseURL: base,
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--unsafely-treat-insecure-origin-as-secure=http://localhost:7001',
      '--disable-features=BlockInsecurePrivateNetworkRequests',
    ],
  })
  await context.grantPermissions(['notifications'], { origin: base })
  await context.addCookies([{ name: 'session', value: session.token, domain: 'localhost', path: '/', httpOnly: true, sameSite: 'Lax' }])
  const page = await context.newPage()
  page.on('console', msg => result.steps.push({ console: msg.type(), text: msg.text().slice(0, 500) }))
  page.on('pageerror', err => result.steps.push({ pageerror: err.message }))
  await page.goto(base + '/', { waitUntil: 'networkidle', timeout: 30000 })
  result.steps.push({ navigation_url: page.url() })
  result.auth = await page.evaluate(async () => fetch('/auth/check', { credentials: 'include' }).then(r => r.json()).catch(e => ({ error: e.message })))

  result.browserPush = await page.evaluate(async () => {
    const out = {
      location: location.href,
      secureContext: isSecureContext,
      notificationPermission: Notification.permission,
      pushManager: 'PushManager' in window,
      serviceWorker: 'serviceWorker' in navigator,
    }
    try { out.permissionsQuery = (await navigator.permissions.query({ name: 'notifications' })).state } catch (e) { out.permissionsQueryError = e.message }
    try {
      const keyResp = await fetch('/api/push/vapid-public-key', { credentials: 'include' })
      out.vapidStatus = keyResp.status
      out.vapid = await keyResp.json()
    } catch (e) { out.vapidError = { name: e.name, message: e.message } }
    function b64ToUint8Array(base64String) {
      const padding = '='.repeat((4 - base64String.length % 4) % 4)
      const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
      const rawData = atob(base64)
      const outputArray = new Uint8Array(rawData.length)
      for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i)
      return outputArray
    }
    try {
      const reg = await navigator.serviceWorker.register('/sw.js')
      await navigator.serviceWorker.ready
      out.registrationScope = reg.scope
      let sub = await reg.pushManager.getSubscription()
      out.existingSubscription = !!sub
      if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8Array(out.vapid.publicKey) })
      out.subscription = sub.toJSON()
      out.endpointPrefix = out.subscription.endpoint?.slice(0, 120)
      const saveResp = await fetch('/api/push/subscribe', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ subscription: out.subscription, userAgent: navigator.userAgent }) })
      out.subscribeStatus = saveResp.status
      out.subscribeBody = await saveResp.text()
      const testResp = await fetch('/api/push/test', { method: 'POST', credentials: 'include' })
      out.testStatus = testResp.status
      out.testBody = await testResp.text()
    } catch (e) { out.flowError = { name: e.name, message: e.message, stack: e.stack } }
    return out
  })

  result.gates.browser_push_permission = result.browserPush.notificationPermission === 'granted' ? 'passed' : 'failed'
  result.gates.browser_push_subscription = result.browserPush.subscription && result.browserPush.subscribeStatus >= 200 && result.browserPush.subscribeStatus < 300 ? 'passed' : 'failed'
  result.gates.browser_push_delivery = result.browserPush.testStatus >= 200 && result.browserPush.testStatus < 300 ? 'passed' : 'failed'
  await context.close()
  console.log(JSON.stringify(result, null, 2))
  if (Object.values(result.gates).some(v => v !== 'passed')) process.exit(2)
}
main().catch(err => { console.error(err); process.exit(1) })
