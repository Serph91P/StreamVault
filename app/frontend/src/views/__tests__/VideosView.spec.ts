import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import VideosView from '../VideosView.vue'
import router from '@/router'

const mocks = vi.hoisted(() => ({
  getAll: vi.fn(),
  deleteMultiple: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  routerResolve: vi.fn<(location: import('vue-router').RouteLocationRaw) => { fullPath: string }>(),
  route: {
    path: '/videos',
    fullPath: '/videos',
    query: {} as Record<string, string>,
  },
}))

vi.mock('vue-router', async importOriginal => ({
  ...await importOriginal<typeof import('vue-router')>(),
  useRouter: () => ({ push: mocks.routerPush, replace: mocks.routerReplace, resolve: mocks.routerResolve }),
  useRoute: () => mocks.route,
}))

vi.mock('@/services/api', () => ({
  videoApi: {
    getAll: mocks.getAll,
    deleteMultiple: mocks.deleteMultiple,
  },
}))

const BaseButtonStub = defineComponent({
  props: ['disabled'],
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})

async function mountView() {
  const wrapper = mount(VideosView, {
    global: {
      directives: { ripple: {} },
      stubs: {
        PageHeader: { template: '<header><slot name="actions" /></header>' },
        BaseButton: BaseButtonStub,
        BaseIconButton: BaseButtonStub,
        LoadingSkeleton: true,
        EmptyState: { props: ['title'], template: '<div class="empty-state">{{ title }}</div>' },
        VideoCard: {
          props: ['video'],
          emits: ['play', 'select'],
          template: '<button class="video-card" @click="$emit(\'play\', video)">{{ video.title }}</button>',
        },
        BaseModal: {
          props: ['modelValue'],
          template: '<section v-if="modelValue" class="modal"><slot /><slot name="footer" /></section>',
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  window.history.replaceState({}, '', '/videos')
  mocks.route.path = '/videos'
  mocks.route.fullPath = '/videos'
  mocks.route.query = {}
  // Resolve against the application's registered routes, including case-sensitive names.
  mocks.routerResolve.mockImplementation(location => router.resolve(location))
  mocks.getAll.mockResolvedValue([
    { id: 11, streamer_id: 1, title: 'Morning run', streamer_name: 'alpha', duration: 3600, file_size: 1024, created_at: '2026-09-23T10:00:00Z', status: 'ready' },
    { id: 12, streamer_id: 2, title: 'Night run', streamer_name: 'beta', duration: 7200, file_size: 2048, created_at: '2026-09-22T10:00:00Z', status: 'ready' },
  ])
  mocks.deleteMultiple.mockResolvedValue([{ success: true }])
})

afterEach(() => vi.clearAllMocks())

describe('VideosView library workflow', () => {
  it('synchronizes a changed grid choice through the real router before opening Play', async () => {
    await router.replace('/videos?q=alpha&streamer=alpha&sort=title&view=list')
    mocks.route.query = { q: 'alpha', streamer: 'alpha', sort: 'title', view: 'list' }
    mocks.routerReplace.mockImplementation(location => router.replace(location))
    const wrapper = await mountView()
    await wrapper.get('[label="Show videos as grid"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toMatchObject({ q: 'alpha', streamer: 'alpha', sort: 'title', view: 'grid' })
    await wrapper.get('.video-card').trigger('click')
    expect(mocks.routerPush).toHaveBeenCalledWith(expect.objectContaining({ name: 'VideoPlayer' }))
    wrapper.unmount()
  })

  it('restores the library search, filters, sort and view encoded by an in-app return URL', async () => {
    mocks.route.query = {
      q: 'alpha',
      streamer: 'alpha',
      date: 'all',
      duration: 'medium',
      sort: 'title',
      view: 'list',
    }

    const wrapper = await mountView()

    expect((wrapper.get('.search-input').element as HTMLInputElement).value).toBe('alpha')
    expect((wrapper.get('[aria-label="Filter videos by streamer"]').element as HTMLSelectElement).value).toBe('alpha')
    expect((wrapper.get('[aria-label="Filter videos by duration"]').element as HTMLSelectElement).value).toBe('medium')
    expect((wrapper.get('[aria-label="Sort videos"]').element as HTMLSelectElement).value).toBe('title')
    expect(wrapper.get('.videos-container').classes()).toContain('view-list')
    expect(wrapper.get('.results-info').text().replace(/\s+/g, ' ')).toContain('Showing 1 video of 2')
  })

  it('searches the loaded catalog and routes playable recordings', async () => {
    const wrapper = await mountView()
    expect(wrapper.findAll('.video-card')).toHaveLength(2)

    await wrapper.get('.search-input').setValue('alpha')
    mocks.routerResolve.mockReturnValueOnce({ fullPath: '/videos?q=alpha&streamer=alpha&sort=title&view=list' })

    expect(wrapper.findAll('.video-card')).toHaveLength(1)
    expect(wrapper.text()).toContain('Morning run')
    expect(wrapper.get('.results-info').text().replace(/\s+/g, ' ')).toContain('Showing 1 video of 2')

    await wrapper.get('.video-card').trigger('click')
    expect(mocks.routerPush).toHaveBeenCalledWith(expect.objectContaining({
      name: 'VideoPlayer',
      params: { streamerId: 1, streamId: 11 },
    }))
    expect(window.location.pathname + window.location.search).toBe('/videos?q=alpha&streamer=alpha&sort=title&view=list')
    expect(window.history.state).toMatchObject({ svrs: 0 })
  })

  it('restores an in-app return scroll only after the asynchronous catalog has rendered', async () => {
    const scrollTo = vi.fn()
    vi.stubGlobal('scrollTo', scrollTo)
    mocks.route.query = { q: 'alpha', sort: 'title', view: 'list' }
    const origin = '/videos?q=alpha&sort=title&view=list'
    mocks.route.fullPath = origin
    window.history.replaceState({ svrs: 480 }, '', origin)

    await mountView()

    expect(scrollTo).toHaveBeenCalledWith(0, 480)
    expect(window.history.state).not.toHaveProperty('svrs')
  })

  it('requires confirmation for bulk deletion and retains the selection after a failure', async () => {
    mocks.deleteMultiple.mockRejectedValueOnce(new Error('Deletion forbidden'))
    const wrapper = await mountView()

    await wrapper.findAll('header button').find(button => button.text().includes('Select'))!.trigger('click')
    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    await wrapper.findAll('header button').find(button => button.text().includes('Delete'))!.trigger('click')
    expect(wrapper.get('.modal').text()).toContain('cannot be undone')

    await wrapper.findAll('.modal button').find(button => button.text().includes('Yes, delete'))!.trigger('click')
    await flushPromises()

    expect(mocks.deleteMultiple).toHaveBeenCalledWith([11])
    expect(wrapper.get('.delete-error').text()).toContain('Deletion forbidden')
    expect(wrapper.text()).toContain('1 selected')
    expect(wrapper.findAll('.video-card')).toHaveLength(2)
  })
})
