import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Router, LocationQueryRaw } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StreamerDetailView from '../StreamerDetailView.vue'
import streamerDetailSource from '../StreamerDetailView.vue?raw'

const mocks = vi.hoisted(() => ({
  getStreamer: vi.fn(),
  getStreams: vi.fn(),
  deleteAllStreams: vi.fn(),
  forceStartRecording: vi.fn(),
  onEvent: vi.fn(() => vi.fn()),
  onEvents: vi.fn(() => vi.fn()),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  scrollIntoView: vi.fn(),
}))

vi.mock('@/services/api', () => ({
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
        BaseModal: true,
        BaseButton: true,
        StreamerSettingsFields: true,
      },
    },
  })
  wrappers.push(wrapper)
  await flushPromises()
  await nextTick()
  return { router, wrapper }
}

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

describe('StreamerDetailView stream history', () => {
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
