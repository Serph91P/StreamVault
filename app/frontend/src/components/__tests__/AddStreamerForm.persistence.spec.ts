import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AddStreamerForm from '../AddStreamerForm.vue'
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('@/composables/useToast', () => ({ useToast: () => toast }))
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks() })

describe('manual channel persistence', () => {
  it.each([true, false])('waits for the POST before emitting completion (ok=%s)', async ok => {
    let finish!: (response: unknown) => void
    const pending = new Promise(resolve => { finish = resolve })
    const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ valid: true, streamer_info: { display_name: 'Synthetic' } }) }).mockReturnValueOnce(pending)
    vi.stubGlobal('fetch', fetch)
    const wrapper = mount(AddStreamerForm, { global: { stubs: { StreamerSettingsFields: true } } })
    await wrapper.get('input').setValue('synthetic')
    await wrapper.get('input').trigger('blur')
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('streamer-added')).toBeUndefined()
    finish({ ok, json: async () => ok ? { id: 42 } : { message: 'rejected' } })
    await flushPromises()
    expect(wrapper.emitted('streamer-added')?.length || 0).toBe(ok ? 1 : 0)
    if (!ok) expect(toast.error).toHaveBeenCalledWith('rejected')
    wrapper.unmount()
  })
})
