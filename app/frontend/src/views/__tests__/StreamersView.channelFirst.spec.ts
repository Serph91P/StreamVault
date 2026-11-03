import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import StreamersView from '../StreamersView.vue'

const api = vi.hoisted(() => ({ getAll: vi.fn() }))
const route = reactive({ query: {} as Record<string, string> })
vi.mock('@/services/api', () => ({ streamersApi: api }))
vi.mock('@/composables/useForceRecording', () => ({ useForceRecording: () => ({ forceStartRecording: vi.fn() }) }))
vi.mock('vue-router', async importOriginal => ({
  ...await importOriginal<typeof import('vue-router')>(),
  useRoute: () => route,
}))

const open = () => mount(StreamersView, {
  global: {
    plugins: [createPinia()],
    directives: { ripple: () => {} },
    stubs: {
      PageHeader: { props: ['title', 'subtitle'], template: '<header><h1>{{ title }}</h1><p>{{ subtitle }}</p><slot name="actions" /></header>' },
      StreamerCard: { props: ['streamer'], template: '<article>{{ streamer.username }}</article>' },
      RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      EmptyState: { props: ['title', 'description'], template: '<section>{{ title }} {{ description }}</section>' },
    },
  },
})

beforeEach(() => {
  route.query = {}
  api.getAll.mockResolvedValue({ streamers: [{ id: 1, username: 'demo_channel', is_live: false, is_recording: false }] })
})

describe('channel-first landing', () => {
  it('preserves channel management, import and add entry points', async () => {
    const wrapper = open()
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Meine Kanäle')
    expect(wrapper.find('a[href="/add-streamer"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/add-streamer/import"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/streamers/manage"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('demo_channel')
    wrapper.unmount()
  })

  it('does not mistake an empty live filter for an empty channel collection', async () => {
    route.query = { filter: 'live' }
    const wrapper = open()
    await flushPromises()
    expect(wrapper.text()).toContain('Keine passenden Kanäle')
    expect(wrapper.text()).not.toContain('Noch keine Kanäle')
    wrapper.unmount()
  })
})
