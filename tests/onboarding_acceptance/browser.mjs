import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'
import assert from 'node:assert/strict'
const { chromium, expect } = createRequire(process.env.FRONTEND_ROOT + '/package.json')('@playwright/test')
const origin = process.env.ACCEPTANCE_ORIGIN, output = process.env.ACCEPTANCE_OUTPUT
const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath(), headless: true })
const result = { scope: 'REAL built wizard → production app factory/router/service/repository → disposable SQLite; synthetic provider only, real generated-admin auth, lifespan off; no API fulfills', controls: [], posts: [], cases: [] }
try {
  const context = await browser.newContext({ serviceWorkers: 'block' })
  const page = await context.newPage(), errors = []
  let transport = 'normal', addPosts = 0, completionPosts = 0
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== origin) return route.abort()
    if (url.pathname === '/auth/onboarding/complete' && request.method() === 'POST') completionPosts++
    if (url.pathname.startsWith('/api/streamers/') && request.method() === 'POST') {
      addPosts++
      result.posts.push({ path: url.pathname, body: request.postData(), contentType: request.headers()['content-type'], transport })
      if (transport === 'abort') return route.abort('failed')
      // Corrupt transport data to exercise the actual registered validation; never fulfill it.
      if (transport === 'invalid') return route.continue({ postData: '[1]', headers: { ...request.headers(), 'content-type': 'application/json' } })
    }
    return route.continue()
  })
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(origin + '/auth/login')
  await page.getByLabel('Username', { exact: true }).fill('onboarding-admin')
  await page.getByLabel('Password', { exact: true }).fill(process.env.ACCEPTANCE_PASSWORD)
  const login = page.waitForResponse(r => r.url().endsWith('/auth/login') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Sign In', exact: true }).click()
  assert.equal((await login).status(), 200)
  await page.waitForURL(url => !url.pathname.endsWith('/auth/login'))
  await page.goto(origin + '/welcome?step=streamers')
  const input = page.getByPlaceholder('Twitch username'), add = page.getByRole('button', { name: 'Add', exact: true })
  await expect(input).toBeVisible()
  const state = async () => { const r = await context.request.get(origin + '/_acceptance/state'); assert.equal(r.status(), 200); return r.json() }
  const initial = await state()
  assert.deepEqual(initial.channels, [])
  // Route negatives run through the factory's registered route and validation.
  for (const [name, data, status] of [
    ['missing', undefined, 422], ['null', 'null', 422], ['array', '[1]', 422],
    ['string', '"invalid"', 422], ['malformed', '{', 422],
  ]) {
    const response = await context.request.post(origin + '/api/streamers/synthetic995', { data: data === undefined ? undefined : Buffer.from(data), headers: { 'Content-Type': 'application/json' } })
    assert.equal(response.status(), status, name)
    result.controls.push({ name, status: response.status() })
  }
  assert.deepEqual((await state()).provider_calls, [])
  const invalidName = await context.request.post(origin + '/api/streamers/%20', { data: {} })
  assert.equal(invalidName.status(), 400)
  result.controls.push({ name: 'blank-name', status: invalidName.status() })
  for (const name of [' ', '@']) {
    await input.fill(name)
    await input.press('Enter')
    assert.equal(addPosts, 0)
  }
  for (const scenario of [
    { name: 'provider rejection', username: 'providerfailure', mode: 'normal', status: 400 },
    { name: 'invalid name', username: 'invalid!name', mode: 'normal', status: 400 },
    { name: 'route validation', username: 'synthetic995', mode: 'invalid', status: 422 },
    { name: 'network failure', username: 'synthetic995', mode: 'abort' },
  ]) {
    transport = scenario.mode
    await input.fill(scenario.username)
    const response = scenario.status ? page.waitForResponse(r => r.url().includes('/api/streamers/') && r.request().method() === 'POST') : null
    await add.click()
    if (response) assert.equal((await response).status(), scenario.status, scenario.name)
    await expect(page.locator('.error-banner')).toBeVisible()
    await expect(input).toHaveValue(scenario.username)
    await expect(input).toBeEnabled()
    await expect(page.locator('.added-streamers')).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Add Streamers', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Skip & Continue', exact: true })).toBeEnabled()
    assert.deepEqual((await state()).channels, [])
    assert.equal((await state()).welcome_completed, false)
    assert.equal(completionPosts, 0)
    result.cases.push({ name: scenario.name, pass: true })
  }
  transport = 'normal'
  await input.fill('  @synthetic995  ')
  const before = addPosts
  const pendingResponse = page.waitForResponse(r => r.url().endsWith('/api/streamers/synthetic995') && r.request().method() === 'POST')
  await add.click()
  // This assertion intentionally fails RED on the bodyless production caller (422).
  await expect.poll(async () => (await state()).provider_calls.filter(name => name === 'synthetic995').length).toBe(1)
  await expect(input).toBeDisabled()
  await expect(add).toBeDisabled()
  await input.evaluate(element => element.form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
  assert.equal(addPosts, before + 1)
  assert.deepEqual((await state()).channels, [])
  await expect(page.locator('.added-streamers')).toHaveCount(0)
  assert.equal((await context.request.post(origin + '/_acceptance/release')).status(), 200)
  assert.equal((await pendingResponse).status(), 200)
  await expect(page.locator('.added-streamers li')).toHaveCount(1)
  await expect(page.locator('.added-streamers')).toHaveText('synthetic995')
  await expect(input).toHaveValue('')
  await expect(input).toBeEnabled()
  await expect(page.locator('.error-banner')).toHaveCount(0)
  const persisted = await state()
  assert.equal(persisted.channels.length, 1)
  assert.equal(persisted.channels[0].username, 'synthetic995')
  assert.equal(persisted.welcome_completed, false)
  assert.equal(persisted.global_codec, initial.global_codec)
  assert.equal(persisted.recording_quality, initial.recording_quality)
  assert.equal(persisted.recording_enabled, initial.recording_enabled)
  assert.equal(persisted.channel_settings.length, 1)
  assert.equal(persisted.channel_settings[0].custom_filename, null)
  assert.equal(persisted.channel_settings[0].use_global_cleanup_policy, true)
  assert.equal(completionPosts, 0)
  const getChannels = async () => { const r = await context.request.get(origin + '/api/streamers'); assert.equal(r.status(), 200); const data = await r.json(); assert.equal(data.streamers.length, 1); assert.equal(data.streamers[0].username, 'synthetic995'); return data }
  result.freshGet = await getChannels()
  await page.screenshot({ path: output + '/confirmed-channel.png', fullPage: true })
  await page.reload()
  await expect(input).toBeVisible()
  result.afterReload = await getChannels()
  assert.deepEqual((await state()).channels, persisted.channels)
  assert.deepEqual(errors, [])
  result.cases.push({ name: 'delayed response, double submit, retry, persisted new-session GET and reload', pass: true })
  result.persisted = persisted
  result.pageErrors = errors
  writeFileSync(output + '/result.json', JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result, null, 2))
  await context.close()
} finally {
  await browser.close()
}
