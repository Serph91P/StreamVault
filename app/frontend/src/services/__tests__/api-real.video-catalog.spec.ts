import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/router', () => ({ default: { push: vi.fn() } }))
vi.mock('@/services/storage', () => ({ appStorage: { clearSessionToken: vi.fn(), clearSessionStorage: vi.fn() } }))

import { videoApi } from '@/services/api-real'

afterEach(() => vi.unstubAllGlobals())

describe('paged video transport', () => {
  it('forwards bounded server query and cancellation without using the legacy catalog', async () => {
    const page = { items: [{ id: 50001, title: 'Outside first page' }], total: 50000, page: 2, page_size: 50, has_more: true }
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(page), { headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', request)
    const abort = new AbortController()
    await expect(videoApi.getPage({ page: 2, page_size: 50, q: '50%_', sort: 'size', order: 'desc' }, abort.signal)).resolves.toEqual(page)
    const [url, options] = request.mock.calls[0]!
    expect(new URL(url, 'http://localhost').pathname).toBe('/api/videos/catalog')
    expect(new URL(url, 'http://localhost').searchParams.get('q')).toBe('50%_')
    expect(new URL(url, 'http://localhost').searchParams.get('page')).toBe('2')
    expect(options).toMatchObject({ signal: abort.signal, credentials: 'include' })
  })

  it('loads a single video outside page one by stream ID', async () => {
    const video = { id: 50001, title: 'Target metadata' }
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(video), { headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', request)
    await expect(videoApi.getMetadata(50001)).resolves.toEqual(video)
    expect(request).toHaveBeenCalledWith('/api/videos/50001/metadata', expect.objectContaining({ method: 'GET' }))
  })
})
