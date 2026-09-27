import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import routeResponse from '../../../tests/fixtures/recording-active-status-contract.json'

const mocks = vi.hoisted(() => ({
  getStreamers: vi.fn(),
  getVideos: vi.fn(),
  getActiveRecordings: vi.fn(),
  getStats: vi.fn(),
  getActiveTasks: vi.fn(),
  getRecentTasks: vi.fn(),
  onEvent: vi.fn<(type: string, callback: (event: { type: string; data?: unknown }) => void) => () => void>(),
  onEvents: vi.fn<(types: string[], callback: (event: { type: string; data?: unknown }) => void) => () => void>(),
  push: vi.fn(),
  forceStartRecording: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  streamersApi: { getAll: mocks.getStreamers },
  videoApi: { getAll: mocks.getVideos },
  recordingApi: { getActiveRecordings: mocks.getActiveRecordings },
  backgroundQueueApi: {
    getStats: mocks.getStats,
    getActiveTasks: mocks.getActiveTasks,
    getRecentTasks: mocks.getRecentTasks,
  },
}))

vi.mock('@/stores/realtime', () => ({
  useRealtimeStore: () => ({
    recentEvents: [],
    onEvent: mocks.onEvent,
    onEvents: mocks.onEvents,
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/composables/useForceRecording', () => ({
  useForceRecording: () => ({ forceStartRecording: mocks.forceStartRecording }),
}))

import HomeView from '../HomeView.vue'

function mountView() {
  return mount(HomeView, {
    global: {
      stubs: {
        BasePanel: { template: '<section><slot name="title" /><slot name="description" /><slot /><slot name="actions" /></section>' },
        EmptyState: {
          props: ['title', 'description', 'retryLabel'],
          template: '<div><strong>{{ title }}</strong><p>{{ description }}</p><button v-if="retryLabel" @click="$emit(\'retry\')">{{ retryLabel }}</button></div>',
        },
        LoadingSkeleton: true,
        StreamerCard: true,
        VideoCard: true,
        StatusBadge: true,
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

beforeEach(() => {
  mocks.getStreamers.mockResolvedValue({ streamers: [] })
  mocks.getVideos.mockResolvedValue([])
  mocks.getActiveRecordings.mockRejectedValue(new Error('recording endpoint unavailable'))
  mocks.getStats.mockResolvedValue({
    total_tasks: 0,
    completed_tasks: 0,
    failed_tasks: 0,
    retried_tasks: 0,
    pending_tasks: 0,
    active_tasks: 0,
    workers: 0,
    is_running: false,
  })
  mocks.getActiveTasks.mockResolvedValue([])
  mocks.getRecentTasks.mockResolvedValue([])
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('HomeView recording status consumer', () => {
  it('keeps a failed active-recordings fetch explicitly unknown and retries through the facade', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Unknown.')
    expect(wrapper.text()).toContain('Retry')

    mocks.getActiveRecordings.mockResolvedValueOnce([])
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mocks.getActiveRecordings).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Recording status is unknown')
  })

  it('renders contract recording status from realtime and unsubscribes it on unmount', async () => {
    type RealtimeCallback = (event: { type: string; data?: unknown }) => void
    const subscriptions: Array<{ type: string; callback: RealtimeCallback; active: boolean; unsubscribe: ReturnType<typeof vi.fn> }> = []

    const subscribe = (types: string[], callback: RealtimeCallback) => {
      const created = types.map((type) => {
        const subscription = {
          type,
          callback,
          active: true,
          unsubscribe: vi.fn(() => { subscription.active = false })
        }
        subscriptions.push(subscription)
        return subscription
      })
      return () => created.forEach((subscription) => subscription.unsubscribe())
    }

    mocks.onEvent.mockImplementation((type: string, callback: RealtimeCallback) => subscribe([type], callback))
    mocks.onEvents.mockImplementation((types: string[], callback: RealtimeCallback) => subscribe(types, callback))
    mocks.getActiveRecordings.mockResolvedValue([])

    let activeRecordingDeliveries = 0
    const dispatch = (type: string, data: unknown) => {
      subscriptions
        .filter((subscription) => subscription.active && subscription.type === type)
        .forEach((subscription) => {
          if (type === 'active_recordings_update') activeRecordingDeliveries += 1
          subscription.callback({ type, data })
        })
    }

    const wrapper = mountView()
    await flushPromises()

    dispatch('active_recordings_update', { recordings: routeResponse })
    await flushPromises()

    expect(wrapper.text()).toContain('pending-channel')
    expect(wrapper.text()).toContain('Authenticated Twitch recording')
    expect(wrapper.text()).toContain('-25')
    expect(wrapper.text()).toContain('awaiting_higher_priority_handoff')
    expect(wrapper.text()).toContain('A short segment-boundary gap may follow this auth handoff.')
    expect(wrapper.text()).toContain('blocked-channel')
    expect(wrapper.text()).toContain('Anonymous Twitch recording')
    expect(wrapper.text()).toContain('17')
    expect(wrapper.text()).toContain('live_playback_owner_not_preemptible')

    wrapper.unmount()
    expect(subscriptions).not.toHaveLength(0)
    expect(subscriptions.every((subscription) => subscription.unsubscribe.mock.calls.length === 1)).toBe(true)
    expect(activeRecordingDeliveries).toBe(1)

    dispatch('active_recordings_update', {
      recordings: [{ id: 26, streamer_name: 'Late realtime update' }]
    })
    expect(activeRecordingDeliveries).toBe(1)
    expect(wrapper.text()).not.toContain('Late realtime update')
  })
})
