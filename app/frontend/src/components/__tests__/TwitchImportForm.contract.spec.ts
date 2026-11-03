import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TwitchImportForm from '../TwitchImportForm.vue'
const mocks = vi.hoisted(() => ({
  route: { query: { auth_success: 'true' } as Record<string, string> }, replace: vi.fn(),
  getCallbackUrl: vi.fn(), getFollowedChannels: vi.fn(), importStreamers: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ replace: mocks.replace }) }))
vi.mock('@/services/api', () => ({ authApi: mocks }))
afterEach(() => vi.clearAllMocks())

describe('Twitch import product contract', () => {
  it('continues a server-stored OAuth callback and imports selected channel objects', async () => {
    const channel = { id: '123', login: 'synthetic', display_name: 'Synthetic' }
    mocks.getCallbackUrl.mockResolvedValue({ url: 'https://example.invalid/api/twitch/callback' })
    mocks.getFollowedChannels.mockResolvedValue({ channels: [channel] })
    mocks.importStreamers.mockResolvedValue({ imported: [{ username: 'synthetic', id: 1 }], already_exists: [], failed: [] })
    const wrapper = mount(TwitchImportForm)
    await flushPromises()
    expect(wrapper.find('.selection-section').exists()).toBe(true)
    expect(wrapper.find('.auth-section').exists()).toBe(false)
    await wrapper.findAll('button').find(button => button.text().trim() === 'Select All')!.trigger('click')
    await wrapper.findAll('button').find(button => button.text().trim() === 'Import 1 Streamers')!.trigger('click')
    await flushPromises()
    expect(mocks.importStreamers).toHaveBeenCalledWith([channel])
    expect(wrapper.emitted('streamers-imported')).toHaveLength(1)
    expect(wrapper.text()).toContain('1')
    expect(mocks.replace).toHaveBeenCalledWith({ query: {} })
    wrapper.unmount()
  })
  it('shows the unwrapped callback URL for authentication errors', async () => {
    mocks.route.query = { error: 'redirect_mismatch' }
    mocks.getCallbackUrl.mockResolvedValue({ url: 'https://example.invalid/api/twitch/callback' })
    const wrapper = mount(TwitchImportForm)
    await flushPromises()
    expect(wrapper.text()).toContain('https://example.invalid/api/twitch/callback')
    wrapper.unmount()
    mocks.route.query = { auth_success: 'true' }
  })
})
