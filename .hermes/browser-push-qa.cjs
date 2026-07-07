const { chromium } = require('playwright')
const { execFileSync } = require('child_process')
const crypto = require('crypto')

const base = 'http://localhost:7001'

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

function b64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = Buffer.from(base64, 'base64')
  return new Uint8Array(rawData)
}

async function main() {
  const session = createSession()
  const result = { base, session: { user_id: session.user_id, username: session.username }, steps: [], gates: {} }
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--unsafely-treat-insecure-origin-as-secure=http://localhost:7001'] })
  const context = await browser.newContext({ baseURL: base })
  await context.grantPermissions(['notifications'], { origin: base })
  await context.addCookies([{ name: 'session', value: session.token, domain: 'localhost', path: '/', httpOnly: true, sameSite: 'Lax' }])
  const page = await context.newPage()
  page.on('console', msg => result.steps.push({ console: msg.type(), text: msg.text().slice(0, 500) }))
  await page.goto(base + '/', { waitUntil: 'networkidle', timeout: 30000 })
  const auth = await page.evaluate(async () => fetch('/auth/check', { credentials: 'include' }).then(r => r.json()))
  result.steps.push({ auth })
  const pushResult = await page.evaluate(async () => {
    const out = { secureContext: window.isSecureContext, permission: Notification.permission, pushManager: 'PushManager' in window, serviceWorker: 'serviceWorker' in navigator }
    const reg = await navigator.serviceWorker.register('/sw.js')
    await navigator.serviceWorker.ready
    out.registrationScope = reg.scope
    const keyResp = await fetch('/api/push/vapid-public-key', { credentials: 'include' })
    out.vapidStatus = keyResp.status
    const keyJson = await keyResp.json()
    out.vapidConfigured = keyJson.configured
    function b64ToUint8Array(base64String) {
      const padding = '='.repeat((4 - base64String.length % 4) % 4)
      const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
      const rawData = atob(base64)
      const outputArray = new Uint8Array(rawData.length)
      for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i)
      return outputArray
    }
    let sub = await reg.pushManager.getSubscription()
    if (!sub) {
      sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8Array(keyJson.publicKey) })
    }
    out.endpointPrefix = sub.endpoint.slice(0, 80)
    const saveResp = await fetch('/api/push/subscribe', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription: sub.toJSON(), userAgent: navigator.userAgent })
    })
    out.subscribeStatus = saveResp.status
    out.subscribeBody = await saveResp.text()
    const testResp = await fetch('/api/push/test', { method: 'POST', credentials: 'include' })
    out.testStatus = testResp.status
    out.testBody = await testResp.text()
    return out
  })
  result.gates.browser_push_subscription = pushResult
  await browser.close()
  console.log(JSON.stringify(result, null, 2))
}

main().catch(err => { console.error(err); process.exit(1) })
