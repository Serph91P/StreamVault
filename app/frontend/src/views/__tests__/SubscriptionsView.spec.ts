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
  mocks.fetch.mockImplementation(() => Promise.resolve(new Response(JSON.stringify([{ id: 1, twitch_id: '42', username: 'alpha' }]), {
    headers: { 'content-type': 'application/json' }
  })))
  vi.stubGlobal('alert', mocks.alert)
  vi.stubGlobal('confirm', mocks.confirm)
  vi.stubGlobal('fetch', mocks.fetch)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SubscriptionsView error recovery (controlled facade, not HTTP)', () => {
  it('distinguishes initial failure from empty success and retries deliberately', async () => {
    mocks.getAll.mockRejectedValueOnce(new Error('list failed'))
    const wrapper = await mountView()
    expect(wrapper.get('[role="alert"]').text()).toContain('Unable to load subscriptions')
    expect(wrapper.text()).not.toContain('No Subscriptions Found')
    expect(mocks.getAll).toHaveBeenCalledTimes(1)

    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(mocks.getAll).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('alpha')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows a confirmed empty response as empty, not an error', async () => {
    mocks.getAll.mockResolvedValueOnce({ total: 0, subscriptions: [] })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('No Subscriptions Found')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('preserves known rows and reports a failed refresh, including malformed success', async () => {
    const wrapper = await mountView()
    for (const outcome of [() => Promise.reject(new TypeError('Failed to fetch')), () => Promise.resolve({})]) {
      mocks.getAll.mockImplementationOnce(outcome)
      await wrapper.get('button.btn-action.btn-secondary').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('alpha')
      expect(wrapper.get('[role="alert"]').text()).toContain('Unable to load subscriptions')
      expect(wrapper.text()).not.toContain('No Subscriptions Found')
    }
    wrapper.unmount()
  })

  it('bounds a pending row delete and releases it for deliberate retry after failure', async () => {
    let rejectDelete!: (reason: Error) => void
    mocks.delete.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectDelete = reject }))
    const wrapper = await mountView()
    await wrapper.get('.btn-delete').trigger('click')
    expect(wrapper.get('.btn-delete').attributes('disabled')).toBeDefined()
    await wrapper.get('.btn-delete').trigger('click')
    // Guard also covers duplicate programmatic invocations, not just disabled DOM.
    void (wrapper.vm as unknown as { deleteSubscription: (id: string) => Promise<void> }).deleteSubscription('sub-1')
    expect(mocks.delete).toHaveBeenCalledTimes(1)
    expect(mocks.confirm).toHaveBeenCalledTimes(1)
    expect(wrapper.get('.btn-action.btn-danger').attributes('disabled')).toBeDefined()
    rejectDelete(new Error('delete failed'))
    await flushPromises()
    expect(wrapper.text()).toContain('alpha')
    expect(wrapper.get('[role="alert"]').text()).toContain('Unable to delete subscription')
    expect(wrapper.get('.btn-delete').attributes('disabled')).toBeUndefined()
    await wrapper.get('.btn-delete').trigger('click')
    await flushPromises()
    expect(mocks.delete).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.btn-delete').exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('cancels without a request and removes only the successfully deleted row', async () => {
    mocks.getAll.mockResolvedValueOnce({ total: 2, subscriptions: [...subscriptions, { ...subscriptions[0], id: 'sub-2' }] })
    const wrapper = await mountView()
    mocks.confirm.mockReturnValueOnce(false)
    await wrapper.findAll('.btn-delete')[0].trigger('click')
    expect(mocks.delete).not.toHaveBeenCalled()
    await wrapper.findAll('.btn-delete')[0].trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(1)
    expect(mocks.delete).toHaveBeenCalledWith('sub-1')
    expect(wrapper.text()).toContain('Total: 1 subscription')
    wrapper.unmount()
  })
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

    await wrapper.get('button.btn-action.btn-secondary').trigger('click')
    await flushPromises()
    expect(mocks.getAll).toHaveBeenCalledTimes(2)

    await wrapper.get('.btn-action.btn-danger').trigger('click')
    await flushPromises()
    expect(mocks.deleteAll).toHaveBeenCalledTimes(1)
    expect(mocks.alert).toHaveBeenCalledWith('All subscriptions successfully deleted!')

    await wrapper.findAll('button.btn-action.btn-secondary')[1].trigger('click')
    await flushPromises()
    expect(mocks.resubscribeAll).toHaveBeenCalledTimes(1)
    expect(mocks.alert).toHaveBeenCalledWith('Success: Resubscribed to 1 streamer(s)')
    expect(mocks.getAll).toHaveBeenCalledTimes(4)
  })

  it('clears loading flags after subscription facade failures', async () => {
    mocks.getAll.mockRejectedValueOnce(new Error('list failed'))
    const wrapper = await mountView()

    expect(wrapper.get('button.btn-action.btn-secondary').attributes('disabled')).toBeUndefined()

    mocks.resubscribeAll.mockRejectedValueOnce(new Error('resubscribe failed'))
    await wrapper.findAll('button.btn-action.btn-secondary')[1].trigger('click')
    await flushPromises()
    expect(wrapper.findAll('button.btn-action.btn-secondary')[1].text()).toContain('Resubscribe All')
    expect(wrapper.findAll('button.btn-action.btn-secondary')[1].attributes('disabled')).toBeUndefined()
    expect(mocks.alert).toHaveBeenCalledWith('Error: resubscribe failed')

    mocks.getAll.mockResolvedValue({ total: 1, subscriptions })
    await wrapper.get('button.btn-action.btn-secondary').trigger('click')
    await flushPromises()
    mocks.deleteAll.mockRejectedValueOnce(new Error('delete all failed'))
    await wrapper.get('.btn-action.btn-danger').trigger('click')
    await flushPromises()
    expect(wrapper.get('button.btn-action.btn-secondary').attributes('disabled')).toBeUndefined()
    expect(mocks.alert).toHaveBeenCalledWith('Error: delete all failed')
  })
})
