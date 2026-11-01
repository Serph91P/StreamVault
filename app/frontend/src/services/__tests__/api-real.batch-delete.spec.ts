import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/router', () => ({ default: { push: vi.fn(() => Promise.resolve()) } }))
vi.mock('@/services/storage', () => ({ appStorage: { clearSessionToken: vi.fn(), clearSessionStorage: vi.fn() } }))

import { videoApi } from '@/services/api-real'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'content-type': 'application/json' },
})

describe('independent batch deletes', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('waits for a late success after an early failure and identifies every outcome without retrying', async () => {
    let finish!: (response: Response) => void
    const late = new Promise<Response>(resolve => { finish = resolve })
    const fetch = vi.fn((url: string) => {
      if (url === '/api/streams/11') return Promise.resolve(json({ success: true }))
      if (url === '/api/streams/12') return Promise.resolve(json({ detail: 'Deletion forbidden' }, 403))
      if (url === '/api/streams/13') return late
      throw new Error(`Unexpected request ${url}`)
    })
    vi.stubGlobal('fetch', fetch)
    let settled = false
    const batch = videoApi.deleteMultiple([11, 12, 13])
    // Observe both paths so the old fail-fast implementation fails an assertion, not an unhandled rejection.
    const observed = batch.then(value => { settled = true; return value }, error => { settled = true; return error })
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(settled).toBe(false)
    finish(json({ success: true }))
    expect(await observed).toEqual([
      { id: 11, status: 'fulfilled', value: { success: true } },
      { id: 12, status: 'rejected', reason: expect.objectContaining({ message: 'Deletion forbidden' }) },
      { id: 13, status: 'fulfilled', value: { success: true } },
    ])
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/streams/11', '/api/streams/12', '/api/streams/13'])
  })

  it.each([true, false])('returns per-ID outcomes when every delete succeeds=%s', async success => {
    vi.stubGlobal('fetch', vi.fn(() => success
      ? Promise.resolve(json({ success: true }))
      : Promise.reject(new TypeError('Network unavailable'))))
    const result = await videoApi.deleteMultiple([11, 12])
    expect(result).toEqual(success
      ? [{ id: 11, status: 'fulfilled', value: { success: true } }, { id: 12, status: 'fulfilled', value: { success: true } }]
      : [{ id: 11, status: 'rejected', reason: expect.any(TypeError) }, { id: 12, status: 'rejected', reason: expect.any(TypeError) }])
    await expect(videoApi.deleteMultiple([])).resolves.toEqual([])
  })
})
