import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import VideosView from '../VideosView.vue'

const mocks = vi.hoisted(() => ({
  getAll: vi.fn(),
  deleteMultiple: vi.fn(),
  routerPush: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.routerPush }),
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
  mocks.getAll.mockResolvedValue([
    { id: 11, streamer_id: 1, title: 'Morning run', streamer_name: 'alpha', duration: 3600, file_size: 1024, created_at: '2026-09-23T10:00:00Z', status: 'ready' },
    { id: 12, streamer_id: 2, title: 'Night run', streamer_name: 'beta', duration: 7200, file_size: 2048, created_at: '2026-09-22T10:00:00Z', status: 'ready' },
  ])
  mocks.deleteMultiple.mockResolvedValue([{ success: true }])
})

afterEach(() => vi.clearAllMocks())

describe('VideosView library workflow', () => {
  it('searches the loaded catalog and routes playable recordings', async () => {
    const wrapper = await mountView()
    expect(wrapper.findAll('.video-card')).toHaveLength(2)

    await wrapper.get('.search-input').setValue('alpha')
    expect(wrapper.findAll('.video-card')).toHaveLength(1)
    expect(wrapper.text()).toContain('Morning run')
    expect(wrapper.get('.results-info').text().replace(/\s+/g, ' ')).toContain('Showing 1 video of 2')

    await wrapper.get('.video-card').trigger('click')
    expect(mocks.routerPush).toHaveBeenCalledWith(expect.objectContaining({
      name: 'VideoPlayer',
      params: { streamerId: 1, streamId: 11 },
    }))
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
