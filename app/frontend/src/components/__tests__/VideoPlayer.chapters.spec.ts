import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import VideoPlayer from '../VideoPlayer.vue'

const mocks = vi.hoisted(() => ({
  getChapters: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  videoApi: { getChapters: mocks.getChapters },
}))

vi.mock('@/composables/useCategoryImages', () => ({
  useCategoryImages: () => ({ getCategoryImage: () => undefined }),
}))

async function mountPlayer() {
  const wrapper = mount(VideoPlayer, {
    props: {
      videoSrc: '/api/videos/42/stream',
      streamId: 42,
    },
    global: {
      stubs: { PlayerStatus: true, PlayerError: true },
    },
  })
  await flushPromises()
  return wrapper
}

describe('VideoPlayer automatic chapters', () => {
  beforeEach(() => {
    mocks.getChapters.mockResolvedValue([
      { id: 1, title: 'Opening', start: 0, end: 600 },
      { id: 2, title: 'Main event', start: 600, end: 900 },
    ])
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads the registered video chapters contract and maps numeric start/end values', async () => {
    const wrapper = await mountPlayer()

    expect(mocks.getChapters).toHaveBeenCalledWith(42)
    const markers = wrapper.findAll('.chapter-marker')
    expect(markers).toHaveLength(2)
    expect(markers[0].attributes('title')).toContain('Opening - 0:00 (10m 0s)')
    expect(markers[1].attributes('title')).toContain('Main event - 10:00 (5m 0s)')
  })

  it('leaves chapters empty when the chapter service fails', async () => {
    mocks.getChapters.mockRejectedValueOnce(new Error('Authentication required'))
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)

    const wrapper = await mountPlayer()

    expect(mocks.getChapters).toHaveBeenCalledWith(42)
    expect(wrapper.findAll('.chapter-marker')).toHaveLength(0)
    expect(warning).toHaveBeenCalledWith(
      'Failed to load auto-generated chapters:',
      expect.any(Error),
    )
  })

  it.each([
    ['zero', []],
    ['default title at zero', [{ id: 1, title: '', start: 0, end: 60 }]],
    ['one long title', [{ id: 1, title: 'Synthetic gypq long chapter title '.repeat(12).trim(), start: 0, end: 60 }]],
    ['many long titles', Array.from({ length: 40 }, (_, index) => ({
      id: index + 1, title: `Synthetic chapter ${index + 1} with gypq `.repeat(4).trim(), start: index * 60, end: (index + 1) * 60,
    }))],
  ] as const)('renders %s chapters without inventing entries or duplicating the selector', async (_name, chapters) => {
    mocks.getChapters.mockResolvedValueOnce(chapters)
    const wrapper = await mountPlayer()
    expect(wrapper.findAll('.chapter-marker')).toHaveLength(chapters.length)
    expect(wrapper.find('.chapters-button').exists()).toBe(chapters.length > 0)
    if (chapters.length > 0) {
      await wrapper.get('.chapters-button').trigger('click')
      expect(wrapper.findAll('[role="dialog"]')).toHaveLength(1)
      expect(wrapper.findAll('.chapter-list .chapter-item')).toHaveLength(chapters.length)
      expect(wrapper.findAll('.chapter-list .chapter-title').map(title => title.text())).toEqual(
        chapters.map((chapter, index) => chapter.title || `Chapter ${index + 1}`),
      )
    }
    wrapper.unmount()
  })

  it('seeks after asynchronously loaded chapters and closes the bounded overlay by Escape or outside click', async () => {
    let resolveChapters!: (chapters: Array<{ id: number; title: string; start: number; end: number }>) => void
    mocks.getChapters.mockImplementationOnce(() => new Promise(resolve => { resolveChapters = resolve }))

    const wrapper = await mountPlayer()
    expect(wrapper.find('.chapters-button').exists()).toBe(false)
    expect(wrapper.findAll('.chapter-marker')).toHaveLength(0)
    resolveChapters([{ id: 1, title: 'Delayed chapter', start: 120, end: 240 }])
    await flushPromises()
    expect(wrapper.findAll('.chapter-marker')).toHaveLength(1)
    const video = wrapper.get('video').element as HTMLVideoElement

    await wrapper.get('.chapters-button').trigger('click')
    expect(wrapper.get('.chapter-overlay').attributes('class')).toContain('chapter-overlay')
    expect(wrapper.get('.chapter-list-panel').attributes('role')).toBe('dialog')
    await wrapper.get('.chapter-list .chapter-item').trigger('click')
    expect(video.currentTime).toBe(120)

    await wrapper.get('.chapters-button').trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(wrapper.find('.chapter-overlay').exists()).toBe(false)

    await wrapper.get('.chapters-button').trigger('click')
    await wrapper.get('.chapter-overlay').trigger('click')
    expect(wrapper.find('.chapter-overlay').exists()).toBe(false)
  })
})
