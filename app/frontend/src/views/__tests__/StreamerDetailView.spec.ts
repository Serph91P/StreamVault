import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createWebHistory, createRouter, RouterView } from 'vue-router'
import type { Router, LocationQueryRaw } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StreamerDetailView from '../StreamerDetailView.vue'
import StreamCard from '@/components/cards/StreamCard.vue'
import streamerDetailSource from '../StreamerDetailView.vue?raw'

const mocks = vi.hoisted(() => ({
  getStreamer: vi.fn(),
  getStreams: vi.fn(),
  deleteAllStreams: vi.fn(),
  deleteStream: vi.fn(),
  forceStartRecording: vi.fn(),
  onEvent: vi.fn(() => vi.fn()),
  onEvents: vi.fn(() => vi.fn()),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  scrollIntoView: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  streamsApi: { delete: mocks.deleteStream },
  streamersApi: {
    get: mocks.getStreamer,
    getStreams: mocks.getStreams,
    deleteAllStreams: mocks.deleteAllStreams,
  },
}))

vi.mock('@/stores/realtime', () => ({
  useRealtimeStore: () => ({
    recentEvents: [],
    onEvent: mocks.onEvent,
    onEvents: mocks.onEvents,
  }),
}))

vi.mock('@/composables/useForceRecording', () => ({
  useForceRecording: () => ({
    forceRecordingStreamerId: { value: null },
    forceStartRecording: mocks.forceStartRecording,
  }),
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: mocks.toastSuccess, error: mocks.toastError }),
}))

const StreamCardStub = defineComponent({
  props: { stream: { type: Object, required: true } },
  setup(props) {
    return () => h('article', {
      class: 'stream-card-stub',
      'data-stream-id': String((props.stream as { id: number }).id),
    })
  },
})

const streams = [
  {
    id: 1,
    streamer_id: 42,
    title: 'Newest ended stream',
    category_name: 'Science',
    started_at: '2026-09-04T10:00:00Z',
    ended_at: '2026-09-04T11:00:00Z',
    recording_path: '/recordings/1.mp4',
  },
  {
    id: 2,
    streamer_id: 42,
    title: 'Newest active stream',
    category_name: 'Chatting',
    started_at: '2026-09-03T10:00:00Z',
    ended_at: null,
    recording_path: '/stale-active.mp4',
  },
  {
    id: 3,
    streamer_id: 42,
    title: 'Oldest ended stream',
    category_name: 'Games',
    started_at: '2026-09-02T10:00:00Z',
    ended_at: '2026-09-02T13:00:00Z',
    recording_path: null,
  },
  {
    id: 4,
    streamer_id: 42,
    title: 'Oldest active stream',
    category_name: 'Music',
    started_at: '2026-09-01T10:00:00Z',
    ended_at: null,
    recording_path: null,
  },
]

const wrappers: VueWrapper[] = []

describe('detail resource failure', () => {
  it('does not claim a missing channel on a server failure and offers retry', async () => {
    mocks.getStreamer.mockRejectedValueOnce(new Error('server unavailable'))
    const { wrapper } = await mountView()
    const feedback = wrapper.getComponent({ name: 'EmptyState' })
    expect(feedback.props('state')).toBe('error')
    expect(feedback.props('retryLabel')).toBe('Erneut versuchen')
  })
})

async function mountView(query: LocationQueryRaw = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/streamers/:id', name: 'streamer-detail', component: { template: '<div />' } },
      { path: '/streamers', component: { template: '<div />' } },
    ],
  })
  await router.push({ name: 'streamer-detail', params: { id: '42' }, query })
  await router.isReady()

  const wrapper = mount(StreamerDetailView, {
    attachTo: document.body,
    global: {
      plugins: [router],
      stubs: {
        StreamCard: StreamCardStub,
        LoadingSkeleton: true,
        EmptyState: true,
        StatusCard: true,
        StatusBadge: true,
        BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue" class="confirm-modal"><slot /><slot name="footer" /></div>' },
        BaseButton: { template: '<button><slot /></button>' },
        StreamerSettingsFields: true,
        ChannelSettingsPanel: true,
      },
    },
  })
  wrappers.push(wrapper)
  await flushPromises()
  await nextTick()
  return { router, wrapper }
}

describe('single stream deletion', () => {
  it.each([true, false])('requires confirmation and removes only a successfully deleted stream (ok=%s)', async ok => {
    const { wrapper } = await mountView({ tab: 'videos' })
    mocks.deleteStream.mockImplementation(async () => { if (!ok) throw new Error('rejected') })
    wrapper.findAllComponents(StreamCardStub).find(card => card.props('stream').id === 1)!.vm.$emit('delete', streams[0])
    await nextTick()
    expect(wrapper.find('.confirm-modal').exists()).toBe(true)
    expect(mocks.deleteStream).not.toHaveBeenCalled()
    const confirm = wrapper.get('.confirm-modal').findAll('button').find(button => button.text().trim() === 'Delete Stream')!
    await confirm.trigger('click')
    await flushPromises()
    expect(mocks.deleteStream).toHaveBeenCalledWith(1)
    expect(wrapper.find('[data-stream-id="1"]').exists()).toBe(!ok)
    if (!ok) expect(mocks.toastError).toHaveBeenCalled()
  })
})

function selectedTab(wrapper: VueWrapper) {
  return wrapper.get('[role="tab"][aria-selected="true"]')
}

function streamIds(wrapper: VueWrapper, section: string) {
  return wrapper.get(section).findAll('[data-stream-id]').map(card => Number(card.attributes('data-stream-id')))
}

async function replaceQuery(router: Router, query: LocationQueryRaw) {
  await router.replace({ name: 'streamer-detail', params: { id: '42' }, query })
  await flushPromises()
}

beforeEach(() => {
  mocks.getStreamer.mockResolvedValue({
    id: 42,
    username: 'streamer-alpha',
    display_name: 'Streamer Alpha',
    is_live: true,
    is_recording: true,
  })
  mocks.getStreams.mockResolvedValue({ streams })
  Object.defineProperty(Element.prototype, 'scrollIntoView', {
    configurable: true,
    value: mocks.scrollIntoView,
  })
})

afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
})

describe('StreamerDetailView tab query synchronization', () => {
  it('hydrates the settings draft from the server on a direct settings deep link', async () => {
    mocks.getStreamer.mockResolvedValueOnce({ id: 42, username: 'saved-channel', recording: { enabled: false, supported_codecs: 'av1' }, notifications: { notify_online: false }, quality: '720p' })
    const { wrapper } = await mountView({ tab: 'settings' })
    expect(wrapper.getComponent({ name: 'StreamerSettingsFields' }).props('modelValue')).toMatchObject({ quality: '720p', recording: { enabled: false, supported_codecs: 'av1' }, notifications: { notify_online: false } })
  })
  it('leaves cleanup inheritance to its dedicated editor and never overwrites it with a stale draft', async () => {
    const { wrapper } = await mountView({ tab: 'settings' })
    expect(wrapper.getComponent({ name: 'StreamerSettingsFields' }).props('excludeFields')).toEqual(['recording.use_global_cleanup_policy'])
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    try {
      await (wrapper.vm as unknown as { saveSettings: () => Promise<void> }).saveSettings()
      expect(JSON.parse(fetchMock.mock.calls[0][1].body).recording).not.toHaveProperty('use_global_cleanup_policy')
    } finally {
      vi.unstubAllGlobals()
    }
  })
  it('reconciles immediate channel changes into the existing draft without discarding unrelated edits', async () => {
    const { wrapper } = await mountView({ tab: 'settings' })
    const fields = wrapper.getComponent({ name: 'StreamerSettingsFields' })
    fields.vm.$emit('update:modelValue', { quality: '1080p', recording: { supported_codecs: 'av1', enabled: true }, notifications: { notify_offline: true } })
    await nextTick()
    const panel = wrapper.getComponent({ name: 'ChannelSettingsPanel' })
    panel.vm.$emit('recordingUpdated', { quality: '720p', enabled: false })
    panel.vm.$emit('notificationsUpdated', { notify_online: false })
    await nextTick()
    expect(fields.props('modelValue')).toEqual({ quality: '1080p', recording: { supported_codecs: 'av1', quality: '720p', enabled: false }, notifications: { notify_offline: true, notify_online: false } })
    ;(wrapper.vm as unknown as { loadSettings: () => void }).loadSettings()
    await nextTick()
    expect(fields.props('modelValue')).toMatchObject({ recording: { quality: '720p', enabled: false }, notifications: { notify_online: false } })
  })
  it('mounts the moved settings with the actual channel ID, only in settings', async () => {
    const { wrapper, router } = await mountView({ tab: 'overview' })
    expect(wrapper.findComponent({ name: 'ChannelSettingsPanel' }).exists()).toBe(false)
    await replaceQuery(router, { tab: 'settings' })
    expect(wrapper.getComponent({ name: 'ChannelSettingsPanel' }).props('streamerId')).toBe(42)
  })
  it.each([
    [{ tab: 'overview' }, 'Overview'],
    [{ tab: 'videos' }, 'Videos'],
    [{ tab: 'settings' }, 'Settings'],
    [{ tab: 'events' }, 'Events'],
    [{}, 'Overview'],
    [{ tab: 'invalid' }, 'Overview'],
  ])('selects the permitted tab for query %j', async (query, label) => {
    const { wrapper } = await mountView(query)

    expect(selectedTab(wrapper).text()).toContain(label)
  })

  it('reacts immediately to external query-only route changes without refetching', async () => {
    const { router, wrapper } = await mountView({ tab: 'videos' })

    await replaceQuery(router, { tab: 'events', source: 'notification' })

    expect(selectedTab(wrapper).text()).toContain('Events')
    expect(mocks.getStreamer).toHaveBeenCalledTimes(1)
    expect(mocks.getStreams).toHaveBeenCalledTimes(1)
  })

  it('uses router.replace for clicks, preserves unrelated query, and removes overview', async () => {
    const { router, wrapper } = await mountView({ tab: 'videos', source: 'notification' })
    const replace = vi.spyOn(router, 'replace')

    await wrapper.get('#streamer-detail-tab-events').trigger('click')
    await flushPromises()
    expect(replace).toHaveBeenCalledWith({ query: { tab: 'events', source: 'notification' } })
    expect(router.currentRoute.value.query).toEqual({ tab: 'events', source: 'notification' })

    await wrapper.get('#streamer-detail-tab-overview').trigger('click')
    await flushPromises()
    expect(replace).toHaveBeenLastCalledWith({ query: { source: 'notification' } })
    expect(router.currentRoute.value.query).toEqual({ source: 'notification' })
  })

  it('uses the same replacement path for roving keys and reveals the selected tab', async () => {
    const { router, wrapper } = await mountView({ tab: 'videos', source: 'keyboard' })
    const replace = vi.spyOn(router, 'replace')
    mocks.scrollIntoView.mockClear()

    await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()

    expect(replace).toHaveBeenCalledWith({ query: { tab: 'settings', source: 'keyboard' } })
    expect(selectedTab(wrapper).text()).toContain('Settings')
    expect(document.activeElement).toBe(wrapper.get('#streamer-detail-tab-settings').element)
    expect(mocks.scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', inline: 'nearest' })
  })
})

describe('StreamerDetailView recording return with real router history', () => {
  it.each(['history', 'streamers'])(
    'restores genuine expanded rows before scroll after unmount/back from %s', async source => {
      const webHistory = createWebHistory()
      const router = createRouter({ history: webHistory, routes: [
        { path: '/streamers/:id', component: StreamerDetailView },
        { path: '/videos/:id', component: { template: '<div>Player</div>' } },
      ] })
      const origin = `/streamers/42?tab=videos&sort=oldest&source=${source}`
      history.replaceState({}, '', origin)
      await router.push(origin)
      await router.isReady()
      const wrapper = mount(RouterView, { attachTo: document.body, global: {
        plugins: [router], stubs: {
          LoadingSkeleton: true, EmptyState: true, StatusCard: true, StatusBadge: true,
          BaseModal: true, BaseButton: true, StreamerSettingsFields: true,
          ChannelSettingsPanel: true,
        },
      } })
      wrappers.push(wrapper)
      const card = (id: number) => wrapper.findAllComponents(StreamCard)
        .find(component => component.props('stream').id === id)!
      const expandedIds = () => wrapper.findAllComponents(StreamCard)
        .filter(component => component.find('.stream-expanded').exists())
        .map(component => component.props('stream').id).sort()
      const atScroll: number[][] = []
      const scrollTo = vi.fn(() => { atScroll.push(expandedIds()) })
      vi.stubGlobal('scrollTo', scrollTo)
      vi.stubGlobal('scrollY', 738)
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => ({ has_recording: true }) }))
      try {
        await flushPromises()
        await card(4).get('.expand-btn').trigger('click')
        await card(3).get('.expand-btn').trigger('click')
        await card(3).get('.expand-btn').trigger('click')
        await card(1).get('.expand-btn').trigger('click')
        expect(expandedIds()).toEqual([1, 4])
        expect(card(1).get('.expand-btn').attributes('aria-expanded')).toBe('true')
        await card(1).get('.btn-watch').trigger('click')
        await flushPromises()
        expect(router.currentRoute.value.path).toBe('/videos/1')
        expect(wrapper.findAllComponents(StreamCard)).toHaveLength(0)
        let release!: (value: { streams: typeof streams }) => void
        mocks.getStreams.mockReturnValueOnce(new Promise(resolve => { release = resolve }))
        router.back()
        await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe(origin))
        await flushPromises()
        expect(scrollTo).not.toHaveBeenCalled()
        release({ streams })
        await flushPromises()
        expect(expandedIds()).toEqual([1, 4])
        expect(card(1).get('.expand-btn').attributes('aria-expanded')).toBe('true')
        expect(card(3).get('.expand-btn').attributes('aria-expanded')).toBe('false')
        expect(card(1).get('.stream-expanded').classes().some(name => name.includes('enter'))).toBe(false)
        expect(scrollTo).toHaveBeenCalledExactlyOnceWith(0, 738)
        expect(atScroll).toEqual([[1, 4]])
        expect(router.currentRoute.value.fullPath).toBe(origin)
        expect(history.state.svre).toBeUndefined()
        await card(1).get('.expand-btn').trigger('click')
        expect(expandedIds()).toEqual([4])
        // Unrelated entry, even with the same row IDs, starts collapsed.
        await router.push('/videos/1')
        await router.push('/streamers/77?tab=videos')
        await flushPromises()
        expect(expandedIds()).toEqual([])
        await router.push('/videos/1')
        await router.push(origin)
        await flushPromises()
        expect(expandedIds()).toEqual([])
      } finally {
        wrapper.unmount()
        wrappers.splice(wrappers.indexOf(wrapper), 1)
        webHistory.destroy()
        vi.unstubAllGlobals()
        history.replaceState({}, '', '/')
      }
    }
  )

  it.each(['newest', 'oldest', 'duration-desc', 'duration-asc'])(
    'remounts with %s and restores origin scroll only after async data and tab reveal', async (sort) => {
      const webHistory = createWebHistory()
      const router = createRouter({ history: webHistory, routes: [
        { path: '/streamers/:id', component: StreamerDetailView },
        { path: '/videos/:id', component: { template: '<div>Player</div>' } },
      ] })
      const scrollTo = vi.fn()
      vi.stubGlobal('scrollTo', scrollTo)
      vi.stubGlobal('scrollY', 738)
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => ({ has_recording: true }) }))
      history.replaceState({}, '', '/streamers/42?tab=videos&source=history')
      await router.push('/streamers/42?tab=videos&source=history')
      await router.isReady()
      const wrapper = mount(RouterView, { attachTo: document.body, global: {
        plugins: [router], stubs: {
          StreamCard: StreamCardStub, LoadingSkeleton: true, EmptyState: true,
          StatusCard: true, StatusBadge: true, BaseModal: true, BaseButton: true,
          StreamerSettingsFields: true,
          ChannelSettingsPanel: true,
        },
      } })
      wrappers.push(wrapper)
      try {
        await flushPromises()
        await wrapper.get('#stream-history-sort').setValue(sort)
        await flushPromises()
        const origin = router.currentRoute.value.fullPath
        // Emit the real card event into the actual View-owned fetch/push path.
        wrapper.findAllComponents(StreamCardStub).find(card => card.props('stream').id === 1)!
          .vm.$emit('watch', streams[0])
        await flushPromises()
        expect(router.currentRoute.value.path).toBe('/videos/1')
        expect(wrapper.find('#stream-history-sort').exists()).toBe(false)
        let release!: (value: { streams: typeof streams }) => void
        mocks.getStreams.mockReturnValueOnce(new Promise(resolve => { release = resolve }))
        scrollTo.mockClear()
        mocks.scrollIntoView.mockClear()
        router.back()
        await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe(origin))
        await flushPromises()
        expect(scrollTo).not.toHaveBeenCalled()
        expect(wrapper.findAllComponents(StreamCardStub)).toHaveLength(0)
        release({ streams })
        await flushPromises()
        expect(wrapper.get<HTMLSelectElement>('#stream-history-sort').element.value).toBe(sort)
        expect(selectedTab(wrapper).text()).toContain('Videos')
        expect(router.currentRoute.value.query.source).toBe('history')
        expect(scrollTo).toHaveBeenCalledExactlyOnceWith(0, 738)
        expect(mocks.scrollIntoView.mock.invocationCallOrder.at(-1))
          .toBeLessThan(scrollTo.mock.invocationCallOrder[0]!)
        expect(history.state.svrs).toBeUndefined()
        // Fresh unrelated history entries must not inherit a previous return.
        scrollTo.mockClear()
        await router.push('/streamers/77?tab=videos')
        await flushPromises()
        expect(wrapper.get<HTMLSelectElement>('#stream-history-sort').element.value).toBe('newest')
        expect(scrollTo).not.toHaveBeenCalled()
      } finally {
        wrapper.unmount()
        wrappers.splice(wrappers.indexOf(wrapper), 1)
        webHistory.destroy()
        vi.unstubAllGlobals()
        history.replaceState({}, '', '/')
      }
    }
  )

  it.each(['oldest', 'duration-desc', 'duration-asc', 'invalid', ['oldest', 'newest']])(
    'reads only a permitted scalar sort query %j and reacts to external changes', async sort => {
      const { router, wrapper } = await mountView({ tab: 'videos', sort, source: 'link' })
      const expected = typeof sort === 'string' && sort !== 'invalid' ? sort : 'newest'
      expect(wrapper.get<HTMLSelectElement>('#stream-history-sort').element.value).toBe(expected)
      await replaceQuery(router, { tab: 'videos', sort: 'oldest', source: 'link' })
      expect(wrapper.get<HTMLSelectElement>('#stream-history-sort').element.value).toBe('oldest')
      await replaceQuery(router, { tab: 'unknown', sort: 'unknown', source: 'link' })
      expect(selectedTab(wrapper).text()).toContain('Overview')
      expect(router.currentRoute.value.query).toEqual({ tab: 'unknown', sort: 'unknown', source: 'link' })
    }
  )
})

describe('StreamerDetailView stream history', () => {
  it.each([
    ['newest', [2, 4], [1, 3]],
    ['oldest', [4, 2], [3, 1]],
    ['duration-desc', [2, 4], [3, 1]],
    ['duration-asc', [2, 4], [1, 3]],
  ])('preserves %s ordering, including stable zero-duration ties', async (sort, active, ended) => {
    const { wrapper } = await mountView({ tab: 'videos', sort: sort as string })
    expect(streamIds(wrapper, '#streamer-detail-in-progress')).toEqual(active)
    expect(streamIds(wrapper, '#streamer-detail-previous-streams')).toEqual(ended)
  })

  it('sorts once and partitions every stream exclusively by ended_at', async () => {
    const { wrapper } = await mountView({ tab: 'videos' })

    expect(streamIds(wrapper, '#streamer-detail-in-progress')).toEqual([2, 4])
    expect(streamIds(wrapper, '#streamer-detail-previous-streams')).toEqual([1, 3])

    const rendered = wrapper.findAll('[data-stream-id]').map(card => Number(card.attributes('data-stream-id')))
    expect(rendered.sort((a, b) => a - b)).toEqual([1, 2, 3, 4])
  })

  it('keeps selected sort order within both partitions', async () => {
    const { wrapper } = await mountView({ tab: 'videos' })

    await wrapper.get('#stream-history-sort').setValue('oldest')
    await flushPromises() // Sort is owned by the asynchronous router replacement.

    expect(streamIds(wrapper, '#streamer-detail-in-progress')).toEqual([4, 2])
    expect(streamIds(wrapper, '#streamer-detail-previous-streams')).toEqual([3, 1])
  })

  it('provides an accessible 44px sort control', async () => {
    const { wrapper } = await mountView({ tab: 'videos' })

    expect(wrapper.get('label[for="stream-history-sort"]').text()).toContain('Sort streams')
    expect(wrapper.get('#stream-history-sort').attributes('aria-label')).toBeUndefined()
    expect(streamerDetailSource).toMatch(/\.sort-select\s*\{[\s\S]*?min-height:\s*44px;/)
  })
})
