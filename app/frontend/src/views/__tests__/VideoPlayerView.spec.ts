import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import VideoPlayerView from '../VideoPlayerView.vue'
import videoPlayerViewSource from '../VideoPlayerView.vue?raw'

const mocks = vi.hoisted(() => ({
  route: { params: { id: '42' } as Record<string, string>, query: {} },
  routerBack: vi.fn(),
  routerPush: vi.fn(),
  getAll: vi.fn(),
  getChapters: vi.fn(),
  getVideoStreamUrl: vi.fn((id: number) => `/api/videos/${id}/stream`),
  createShareToken: vi.fn(),
  delete: vi.fn(),
  seekToChapter: vi.fn()
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ back: mocks.routerBack, push: mocks.routerPush })
}))

vi.mock('@/services/api', () => ({
  videoApi: {
    getAll: mocks.getAll,
    getChapters: mocks.getChapters,
    getVideoStreamUrl: mocks.getVideoStreamUrl,
    createShareToken: mocks.createShareToken,
    delete: mocks.delete
  }
}))

const VideoPlayerStub = defineComponent({
  name: 'VideoPlayer',
  props: ['videoSrc', 'chapters', 'streamTitle', 'streamId'],
  setup(props, { expose }) {
    expose({ seekToChapter: mocks.seekToChapter })
    return () => h('div', {
      class: 'video-player-stub',
      'data-src': props.videoSrc,
      'data-title': props.streamTitle
    })
  }
})

async function mountView() {
  const wrapper = mount(VideoPlayerView, {
    global: {
      directives: { ripple: {} },
      stubs: {
        VideoPlayer: VideoPlayerStub,
        GlassCard: { template: '<section><slot /></section>' },
        LoadingSkeleton: true,
        PlayerStatus: true,
        PlayerError: {
          props: ['message', 'actionLabel'],
          emits: ['action'],
          template: '<div class="player-error"><p>{{ message }}</p><button class="retry" @click="$emit(\'action\')">{{ actionLabel }}</button></div>'
        },
        BaseModal: {
          props: ['modelValue'],
          template: '<div v-if="modelValue" class="modal-stub"><slot /><slot name="footer" /></div>'
        },
        BaseButton: { template: '<button class="base-button" @click="$emit(\'click\')"><slot /></button>' }
      }
    }
  })
  await flushPromises()
  await nextTick()
  return wrapper
}

beforeEach(() => {
  mocks.route.params = { id: '42' }
  mocks.route.query = {}
  mocks.getAll.mockResolvedValue([{
    id: 42,
    title: 'Backend title',
    streamer_name: 'backend-streamer',
    duration: 900,
    created_at: '2026-09-01T12:00:00Z'
  }])
  mocks.getChapters.mockResolvedValue([
    { id: 1, title: 'Start', start: 0, end: 600 },
    { id: 2, title: 'Ten minutes', start: 600, end: 900 }
  ])
  mocks.createShareToken.mockResolvedValue({
    success: true,
    share_url: 'https://streamvault.example/shared/42',
    expires_in: '12 hours'
  })
  mocks.delete.mockResolvedValue({ success: true })
  mocks.routerPush.mockResolvedValue(undefined)
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })))
})

afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('VideoPlayerView backend playback contract', () => {
  it.each([
    ['primary route', { id: '42' }],
    ['legacy route', { streamerId: '7', streamId: '42' }]
  ])('loads numeric backend chapters for the %s', async (_name, params) => {
    mocks.route.params = params
    const wrapper = await mountView()

    expect(mocks.getChapters).toHaveBeenCalledWith(42)
    expect(mocks.getAll).toHaveBeenCalledTimes(1)
    expect(mocks.getVideoStreamUrl).toHaveBeenCalledWith(42)
    expect(wrapper.get('.video-player-stub').attributes('data-src')).toBe('/api/videos/42/stream')
    expect(wrapper.text()).toContain('Backend title')
    expect(wrapper.text()).toContain('15:00')
    expect(wrapper.text()).toContain('Sep 1, 2026')
    expect(wrapper.text()).toContain('0:00')
    expect(wrapper.text()).toContain('10:00')

    await wrapper.findAll('.chapter-item')[1].trigger('click')
    expect(mocks.seekToChapter).toHaveBeenCalledWith(600)
  })

  it('shows a retryable error and never substitutes demo playback', async () => {
    mocks.getChapters.mockRejectedValueOnce(new Error('Authentication required'))
    const wrapper = await mountView()

    expect(wrapper.get('.player-error').text()).toContain('Authentication required')
    expect(wrapper.find('.video-player-stub').exists()).toBe(false)
    expect(videoPlayerViewSource).not.toContain('BigBuckBunny')
    expect(videoPlayerViewSource).not.toContain('596')

    await wrapper.get('.retry').trigger('click')
    await flushPromises()
    expect(mocks.getChapters).toHaveBeenCalledTimes(2)
    expect(wrapper.get('.video-player-stub').attributes('data-src')).toBe('/api/videos/42/stream')
  })

  it('routes share and delete actions through the video facade', async () => {
    const wrapper = await mountView()
    const actionButtons = wrapper.findAll('.action-btn')

    await actionButtons[1].trigger('click')
    await flushPromises()
    expect(mocks.createShareToken).toHaveBeenCalledWith(42, {})
    expect(wrapper.get('.share-url-input').attributes('value')).toBe('https://streamvault.example/shared/42')
    expect(wrapper.text()).toContain('12 hours')

    await actionButtons[2].trigger('click')
    await nextTick()
    await wrapper.findAll('.base-button')[1].trigger('click')
    await flushPromises()
    expect(mocks.delete).toHaveBeenCalledWith(42)
    expect(mocks.routerPush).toHaveBeenCalledWith({ name: 'Videos' })
    expect(videoPlayerViewSource).not.toMatch(/fetch\s*\(/)
  })

  it('rejects incomplete catalog metadata instead of inventing values', async () => {
    mocks.getAll.mockResolvedValueOnce([{ id: 42, title: 'Missing metadata' }])
    const wrapper = await mountView()

    expect(wrapper.get('.player-error').text()).toContain('Video metadata is incomplete')
    expect(wrapper.find('.video-player-stub').exists()).toBe(false)
  })
})
