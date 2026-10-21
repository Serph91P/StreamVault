import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getImage: vi.fn(), preloadImages: vi.fn() }))
vi.mock('@/services/api', () => ({ categoriesApi: api }))

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
})

describe('shared category artwork cache', () => {
  it.each([null, ''])('caches the icon fallback when the backend has no image (%s)', async imageUrl => {
    api.getImage.mockResolvedValue({ category_name: 'Synthetic unknown category', image_url: imageUrl })
    const { useCategoryImages } = await import('../useCategoryImages')
    const firstConsumer = useCategoryImages()
    expect(firstConsumer.getCategoryImage('Synthetic unknown category')).toBe('icon:gamepad')
    await flushPromises()
    const secondConsumer = useCategoryImages()
    expect(secondConsumer.getCategoryImage('Synthetic unknown category')).toBe('icon:gamepad')
    await flushPromises()
    expect(api.getImage).toHaveBeenCalledTimes(1)
  })
})
