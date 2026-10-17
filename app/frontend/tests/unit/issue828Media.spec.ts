// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'
import type { Route } from '@playwright/test'
import { localSeekMedia } from '../fixtures/media/issue828Media'

describe('issue 828 local synthetic media transport', () => {
  it.each([
    [undefined, 200, 3257, undefined],
    ['bytes=100-199', 206, 100, 'bytes 100-199/3257'],
    ['bytes=3200-', 206, 57, 'bytes 3200-3256/3257'],
  ])('serves %s without pretending partial content is a full response', async (range, status, length, contentRange) => {
    const fulfill = vi.fn()
    await localSeekMedia({ request: () => ({ headers: () => ({ range }) }), fulfill } as unknown as Route)
    expect(fulfill).toHaveBeenCalledWith(expect.objectContaining({
      status,
      contentType: 'video/mp4',
      headers: expect.objectContaining({ 'Accept-Ranges': 'bytes', 'Content-Length': String(length) }),
    }))
    const response = fulfill.mock.calls[0][0]
    expect(response.body.length).toBe(length)
    expect(response.headers['Content-Range']).toBe(contentRange)
  })

  it('rejects an unsatisfiable byte range', async () => {
    const fulfill = vi.fn()
    await localSeekMedia({ request: () => ({ headers: () => ({ range: 'bytes=9999-' }) }), fulfill } as unknown as Route)
    expect(fulfill).toHaveBeenCalledWith({ status: 416, headers: { 'Content-Range': 'bytes */3257' } })
  })
})
