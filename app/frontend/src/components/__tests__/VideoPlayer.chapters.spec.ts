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
    // jsdom has no modal top-layer implementation; real hit testing remains
    // covered by the unchanged browser chapter-click regression.
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: vi.fn(function (this: HTMLDialogElement) { this.open = true }) })
    Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: vi.fn(function (this: HTMLDialogElement) { this.open = false }) })
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
      expect(wrapper.findAll('dialog, [role="dialog"]')).toHaveLength(1)
      expect(wrapper.findAll('.chapter-list .chapter-item')).toHaveLength(chapters.length)
      expect(wrapper.findAll('.chapter-list .chapter-title').map(title => title.text())).toEqual(
        chapters.map((chapter, index) => chapter.title || `Chapter ${index + 1}`),
      )
    }
    wrapper.unmount()
  })

  it('uses preloaded numeric chapters and clears them when delayed props become empty', async () => {
    const wrapper = mount(VideoPlayer, {
      props: { videoSrc: '/api/videos/42/stream', streamId: 42, chapters: [{ start: 1.25, end: 4.75, title: 'Preloaded' }] },
      global: { stubs: { PlayerStatus: true, PlayerError: true } },
    })
    await flushPromises()
    expect(mocks.getChapters).not.toHaveBeenCalled()
    await wrapper.get('.chapters-button').trigger('click')
    await wrapper.get('.chapter-item').trigger('click')
    expect((wrapper.get('video').element as HTMLVideoElement).currentTime).toBe(1.25)
    await wrapper.setProps({ chapters: [] })
    expect(wrapper.find('.chapters-button').exists()).toBe(false)
    expect(wrapper.find('.chapter-list-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each(['cancel', 'button', 'toggle', 'empty props'] as const)('closes the native modal before Vue removes it via %s, and reopens safely', async (method) => {
    const wrapper = await mountPlayer()
    await wrapper.get('.chapters-button').trigger('click')
    const dialog = wrapper.get('dialog').element as HTMLDialogElement
    expect(dialog.open).toBe(true)
    if (method === 'cancel') await wrapper.get('dialog').trigger('cancel')
    else if (method === 'button') await wrapper.get('.close-btn').trigger('click')
    else if (method === 'toggle') {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'c' }))
      await flushPromises()
    } else await wrapper.setProps({ chapters: [] })
    expect(HTMLDialogElement.prototype.close).toHaveBeenCalledOnce()
    expect(dialog.open, 'modal must no longer leave the opener inert').toBe(false)
    expect(wrapper.find('dialog').exists()).toBe(false)
    if (method === 'empty props') await wrapper.setProps({ chapters: [{ start: 0, end: 60 }] })
    await wrapper.get('.chapters-button').trigger('click')
    expect((wrapper.get('dialog').element as HTMLDialogElement).open).toBe(true)
    wrapper.unmount()
  })

  it('contains Tab at both native chapter dialog boundaries', async () => {
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    const wrapper = mount(VideoPlayer, {
      attachTo: document.body,
      props: { videoSrc: '/api/videos/42/stream', streamId: 42 },
      global: { stubs: { PlayerStatus: true, PlayerError: true } },
    })
    try {
      await flushPromises()
      await wrapper.get('.chapters-button').trigger('click')
      const dialog = wrapper.get('dialog')
      const first = dialog.get('.close-btn').element as HTMLButtonElement
      const last = dialog.findAll('.chapter-item').at(-1)!.element as HTMLButtonElement
      first.focus()
      await dialog.trigger('keydown', { key: 'Tab', shiftKey: true })
      expect(document.activeElement).toBe(last)
      await dialog.trigger('keydown', { key: 'Tab' })
      expect(document.activeElement).toBe(first)
      // Interior keys must retain native navigation; this is not a second modal lifecycle.
      const interior = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
      first.dispatchEvent(interior)
      expect(interior.defaultPrevented).toBe(false)
    } finally {
      wrapper.unmount()
    }
  })

  it('opens chapters in the native modal top layer, independent of page stacking and fullscreen', async () => {
    const showModal = HTMLDialogElement.prototype.showModal
    const wrapper = await mountPlayer()
    await wrapper.get('.chapters-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.chapter-list-panel').element).toBeInstanceOf(HTMLDialogElement)
    expect(showModal).toHaveBeenCalledOnce()
    await wrapper.get('.chapter-list-panel').trigger('cancel')
    expect(wrapper.find('.chapter-list-panel').exists()).toBe(false)
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
    expect(wrapper.get('.chapter-list-panel').element).toBeInstanceOf(HTMLDialogElement)
    expect(wrapper.get('.chapter-list-panel').attributes('aria-label')).toBe('Chapters')
    await wrapper.get('.chapter-list .chapter-item').trigger('click')
    expect(video.currentTime).toBe(120)

    // jsdom does not translate Escape into native dialog cancel. The real
    // browser keeps the physical Escape/focus-return assertion unchanged.
    await wrapper.get('dialog').trigger('cancel')
    await flushPromises()
    expect(wrapper.find('.chapter-list-panel').exists()).toBe(false)

    await wrapper.get('.chapters-button').trigger('click')
    vi.spyOn(wrapper.get('dialog').element, 'getBoundingClientRect').mockReturnValue({ left: 10, right: 100, top: 10, bottom: 100 } as DOMRect)
    await wrapper.get('dialog').trigger('click', { clientX: 50, clientY: 50 })
    expect((wrapper.get('dialog').element as HTMLDialogElement).open).toBe(true)
    await wrapper.get('dialog').trigger('click', { clientX: 2, clientY: 2 })
    expect(wrapper.find('.chapter-list-panel').exists()).toBe(false)
    wrapper.unmount()
  })
})
