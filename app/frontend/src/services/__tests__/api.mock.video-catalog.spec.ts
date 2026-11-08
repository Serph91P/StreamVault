import { afterEach, describe, expect, it, vi } from 'vitest'

vi.hoisted(() => vi.stubEnv('VITE_USE_MOCK_DATA', 'true'))
vi.mock('@/router', () => ({ default: { push: vi.fn() } }))

import { videoApi } from '@/services/api'
import { mockVideos } from '@/mocks/mockData'

afterEach(() => vi.unstubAllGlobals())

describe('mock paged catalog contract', () => {
  it('keeps global totals/facets independent from the current page', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    const first = await videoApi.getPage({ page: 1, page_size: 2, sort: 'title' })
    const second = await videoApi.getPage({ page: 2, page_size: 2, sort: 'title' })
    expect(first.items).toHaveLength(2)
    expect(first.total).toBe(mockVideos.length)
    expect(first.summary.total).toBe(mockVideos.length)
    expect(first.summary.streamers.length).toBeGreaterThanOrEqual(2)
    expect(second.items.map(item => item.id).some(id => first.items.some(item => item.id === id))).toBe(false)
    expect((await videoApi.getPage({ q: '%' })).items).toEqual([])
    const target = mockVideos.at(-1)!
    expect((await videoApi.getMetadata(target.id)).id).toBe(target.id)
    await expect(videoApi.getMetadata(-1)).rejects.toMatchObject({ status: 404 })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('rejects invalid bounded pages and honours cancellation', async () => {
    await expect(videoApi.getPage({ page_size: 10000 })).rejects.toMatchObject({ status: 422 })
    const abort = new AbortController()
    abort.abort()
    await expect(videoApi.getPage({}, abort.signal)).rejects.toMatchObject({ name: 'AbortError' })
  })
})
