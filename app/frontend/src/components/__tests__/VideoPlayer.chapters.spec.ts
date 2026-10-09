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
})
