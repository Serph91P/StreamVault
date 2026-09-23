import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SubscriptionsView from '../SubscriptionsView.vue'
import subscriptionsViewSource from '../SubscriptionsView.vue?raw'

const mocks = vi.hoisted(() => ({
  getAll: vi.fn(),
  resubscribeAll: vi.fn(),
  delete: vi.fn(),
  deleteAll: vi.fn(),
  alert: vi.fn(),
  confirm: vi.fn(),
  fetch: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  subscriptionsApi: {
    getAll: mocks.getAll,
    resubscribeAll: mocks.resubscribeAll,
    delete: mocks.delete,
    deleteAll: mocks.deleteAll,
  }
}))

const subscriptions = [{
  id: 'sub-1',
  type: 'stream.online',
  status: 'enabled',
  created_at: '2026-09-23T12:00:00Z',
  condition: { broadcaster_user_id: '42' }
}]

async function mountView() {
  const wrapper = mount(SubscriptionsView, {
    global: {
      directives: {
        ripple: {},
      },
      stubs: {
        GlassCard: { template: '<div><slot /></div>' },
        LoadingSkeleton: true,
        EmptyState: true,
      },
    },
  })
  await flushPromises()
  await nextTick()
  return wrapper
}

beforeEach(() => {
  mocks.getAll.mockResolvedValue({ total: 1, subscriptions })
  mocks.resubscribeAll.mockResolvedValue({ success: true, message: 'Resubscribed to 1 streamer(s)' })
  mocks.delete.mockResolvedValue({ success: true, message: 'Subscription sub-1 deleted' })
  mocks.deleteAll.mockResolvedValue({ success: true, total_deleted: 1, total_failed: 0 })
  mocks.confirm.mockReturnValue(true)
  mocks.fetch.mockResolvedValue(new Response(JSON.stringify([{ id: 1, twitch_id: '42', username: 'alpha' }]), {
    headers: { 'content-type': 'application/json' }
  }))
  vi.stubGlobal('alert', mocks.alert)
  vi.stubGlobal('confirm', mocks.confirm)
  vi.stubGlobal('fetch', mocks.fetch)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SubscriptionsView facade actions', () => {
  it('has no direct subscription fetches and routes each action through subscriptionsApi', async () => {
    const wrapper = await mountView()

    expect(subscriptionsViewSource).not.toMatch(/fetch\(['"`]\/api\/streamers\/(?:subscriptions|resubscribe-all)/)
    expect(mocks.getAll).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('alpha')

    await wrapper.get('.btn-delete').trigger('click')
    await flushPromises()
    expect(mocks.confirm).toHaveBeenCalledWith('Are you sure you want to delete this subscription? This action cannot be undone.')
    expect(mocks.delete).toHaveBeenCalledWith('sub-1')
    expect(wrapper.find('.btn-delete').exists()).toBe(false)

    await wrapper.get('.btn-action.btn-secondary').trigger('click')
    await flushPromises()
    expect(mocks.getAll).toHaveBeenCalledTimes(2)

    await wrapper.get('.btn-action.btn-danger').trigger('click')
    await flushPromises()
    expect(mocks.deleteAll).toHaveBeenCalledTimes(1)
    expect(mocks.alert).toHaveBeenCalledWith('All subscriptions successfully deleted!')

    await wrapper.findAll('.btn-action.btn-secondary')[1].trigger('click')
    await flushPromises()
    expect(mocks.resubscribeAll).toHaveBeenCalledTimes(1)
    expect(mocks.alert).toHaveBeenCalledWith('Success: Resubscribed to 1 streamer(s)')
    expect(mocks.getAll).toHaveBeenCalledTimes(4)
  })

  it('clears loading flags after subscription facade failures', async () => {
    mocks.getAll.mockRejectedValueOnce(new Error('list failed'))
    const wrapper = await mountView()

    expect(wrapper.get('.btn-action.btn-secondary').attributes('disabled')).toBeUndefined()

    mocks.resubscribeAll.mockRejectedValueOnce(new Error('resubscribe failed'))
    await wrapper.findAll('.btn-action.btn-secondary')[1].trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.btn-action.btn-secondary')[1].text()).toContain('Resubscribe All')
    expect(wrapper.findAll('.btn-action.btn-secondary')[1].attributes('disabled')).toBeUndefined()
    expect(mocks.alert).toHaveBeenCalledWith('Error: resubscribe failed')

    mocks.getAll.mockResolvedValue({ total: 1, subscriptions })
    await wrapper.get('.btn-action.btn-secondary').trigger('click')
    await flushPromises()
    mocks.deleteAll.mockRejectedValueOnce(new Error('delete all failed'))
    await wrapper.get('.btn-action.btn-danger').trigger('click')
    await flushPromises()
    expect(wrapper.get('.btn-action.btn-secondary').attributes('disabled')).toBeUndefined()
    expect(mocks.alert).toHaveBeenCalledWith('Error: delete all failed')
  })
})
