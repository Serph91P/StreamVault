import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import VideosView from '../VideosView.vue'

const mocks = vi.hoisted(() => ({
  getPage: vi.fn(), getMetadata: vi.fn(), deleteMultiple: vi.fn(),
  query: { page: '2' } as Record<string, string>,
}))
vi.mock('vue-router', async original => ({
  ...await original<typeof import('vue-router')>(),
  useRoute: () => ({ query: mocks.query }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), resolve: (location: { query: Record<string, string> }) => ({ fullPath: `/videos?${new URLSearchParams(location.query)}` }) }),
}))
vi.mock('@/services/api', () => ({ videoApi: mocks }))

function page(items = [{ id: 101, title: 'Page two', streamer_id: 1, streamer_name: 'alpha' }], number = 2) {
  return { items, total: 100, page: number, page_size: 50, has_more: number < 3,
    summary: { total: 50000, file_size: 1048576, duration: 7200, streamers: [{ id: 1, name: 'alpha', count: 25000 }, { id: 2, name: 'zeta', count: 25000 }], categories: ['global-category'] },
    index: { pending: 0, error: 0, missing: 0, complete: true, oldest_checked_at: null, page_revalidation_changed: false, retry_required: false },
  }
}
function view() {
  return mount(VideosView, { global: { directives: { ripple: {} }, stubs: {
    PageHeader: { template: '<header><slot name="actions" /></header>' },
    BaseButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
    BaseIconButton: { template: '<button><slot /></button>' }, LoadingSkeleton: true,
    VideoCard: { props: ['video'], template: '<div class="video-card">{{ video.title }}</div>' },
    BaseModal: { props: ['modelValue'], template: '<section v-if="modelValue" class="modal"><slot /><slot name="footer" /></section>' },
    EmptyState: { props: ['title'], template: '<p>{{ title }}</p>' },
  } } })
}

beforeEach(() => {
  mocks.query = { page: '2' }
  mocks.getPage.mockReset().mockResolvedValue(page())
  mocks.getMetadata.mockReset()
  mocks.deleteMultiple.mockReset()
})
afterEach(() => vi.clearAllMocks())

describe('server paged library workflow', () => {
  it('restores page, uses global facets/totals and clears selection on page change', async () => {
    const wrapper = view()
    await flushPromises()
    expect(mocks.getPage).toHaveBeenCalledWith(expect.objectContaining({ page: 2, page_size: 50 }), expect.any(AbortSignal))
    expect(wrapper.get('[aria-label="Filter videos by streamer"]').text()).toContain('zeta')
    expect(wrapper.get('.brief-stats').text()).toContain('50000')
    await wrapper.findAll('header button').find(button => button.text().includes('Select'))!.trigger('click')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    mocks.getPage.mockResolvedValueOnce(page([{ id: 201, title: 'Page three', streamer_id: 1, streamer_name: 'alpha' }], 3))
    await wrapper.get('[aria-label="Next video page"]').trigger('click')
    await flushPromises()
    expect(mocks.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 3 }), expect.any(AbortSignal))
    expect(wrapper.findAll('input:checked')).toHaveLength(0)
    expect(wrapper.text()).toContain('Page three')
    wrapper.unmount()
  })

  it('debounces search, aborts old requests and ignores stale responses', async () => {
    const wrapper = view()
    await flushPromises()
    let finishOld!: (result: ReturnType<typeof page>) => void
    mocks.getPage.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    await wrapper.get('.search-input').setValue('old')
    await new Promise(resolve => setTimeout(resolve, 350))
    const oldSignal = mocks.getPage.mock.calls.at(-1)![1] as AbortSignal
    mocks.getPage.mockResolvedValueOnce(page([{ id: 301, title: 'Fresh result', streamer_id: 1, streamer_name: 'alpha' }], 1))
    await wrapper.get('.search-input').setValue('fresh')
    await new Promise(resolve => setTimeout(resolve, 350))
    await flushPromises()
    expect(oldSignal.aborted).toBe(true)
    expect(mocks.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'fresh', page: 1 }), expect.any(AbortSignal))
    finishOld(page([{ id: 401, title: 'Stale result', streamer_id: 1, streamer_name: 'alpha' }], 1))
    await flushPromises()
    expect(wrapper.text()).toContain('Fresh result')
    expect(wrapper.text()).not.toContain('Stale result')
    wrapper.unmount()
  })

  it('checks failed delete survivors by metadata even when the refreshed page omits them', async () => {
    mocks.getPage.mockResolvedValueOnce(page([{ id: 11, title: 'Delete one', streamer_id: 1, streamer_name: 'alpha' }, { id: 12, title: 'Keep failed', streamer_id: 1, streamer_name: 'alpha' }]))
    const wrapper = view()
    await flushPromises()
    await wrapper.findAll('header button').find(button => button.text().includes('Select'))!.trigger('click')
    for (const checkbox of wrapper.findAll('input[type="checkbox"]')) await checkbox.setValue(true)
    await wrapper.findAll('header button').find(button => button.text().includes('Delete'))!.trigger('click')
    mocks.deleteMultiple.mockResolvedValueOnce([{ id: 11, status: 'fulfilled' }, { id: 12, status: 'rejected', reason: new Error('Denied') }])
    mocks.getPage.mockResolvedValueOnce(page([{ id: 13, title: 'Another page member', streamer_id: 1, streamer_name: 'alpha' }]))
    mocks.getMetadata.mockResolvedValueOnce({ id: 12, title: 'Keep failed' })
    await wrapper.findAll('.modal button').find(button => button.text().includes('Yes, delete'))!.trigger('click')
    await flushPromises()
    expect(mocks.getMetadata).toHaveBeenCalledWith(12)
    expect(wrapper.text()).toContain('1 selected')
    expect(wrapper.get('.delete-error').text()).toContain('1 failed')
    wrapper.unmount()
  })
})
