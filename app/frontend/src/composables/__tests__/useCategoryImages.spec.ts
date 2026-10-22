import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getImage: vi.fn(), preloadImages: vi.fn() }))
vi.mock('@/services/api', () => ({ categoriesApi: api }))

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
})
afterEach(() => vi.restoreAllMocks())

describe('shared category artwork cache', () => {
  it('shares a pending request and its local cache URL across consumers', async () => {
    let finish!: (value: { image_url: string }) => void
    api.getImage.mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const { useCategoryImages } = await import('../useCategoryImages')
    const first = useCategoryImages()
    const second = useCategoryImages()
    first.getCategoryImage('Synthetic shared category')
    second.getCategoryImage('Synthetic shared category')
    expect(api.getImage).toHaveBeenCalledTimes(1)
    finish({ image_url: '/api/media/categories/synthetic-cache.jpg' })
    await flushPromises()
    expect(first.getCategoryImage('Synthetic shared category')).toBe('/api/media/categories/synthetic-cache.jpg')
    expect(second.getCategoryImage('Synthetic shared category')).toBe('/api/media/categories/synthetic-cache.jpg')
    expect(api.getImage).toHaveBeenCalledTimes(1)
  })

  it('keeps a useful fallback after a network failure without retrying on render', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    api.getImage.mockRejectedValue(new Error('Synthetic offline'))
    const { useCategoryImages } = await import('../useCategoryImages')
    const { getCategoryImage } = useCategoryImages()
    expect(getCategoryImage('Synthetic offline category')).toBe('icon:gamepad')
    await flushPromises()
    expect(getCategoryImage('Synthetic offline category')).toBe('icon:gamepad')
    expect(api.getImage).toHaveBeenCalledTimes(1)
  })

  it('does not request artwork when category provenance is absent', async () => {
    const { useCategoryImages } = await import('../useCategoryImages')
    expect(useCategoryImages().getCategoryImage('')).toBe('/images/categories/default-category.svg')
    expect(api.getImage).not.toHaveBeenCalled()
  })

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
