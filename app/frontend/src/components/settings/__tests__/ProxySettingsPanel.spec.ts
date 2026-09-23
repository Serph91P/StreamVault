import { flushPromises, shallowMount } from '@vue/test-utils'
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const actions = vi.hoisted(() => ({
  fetchProxies: vi.fn(),
  addProxy: vi.fn(),
  deleteProxy: vi.fn(),
  toggleProxy: vi.fn(),
  testProxy: vi.fn(),
  updatePriority: vi.fn(),
  updateConfig: vi.fn(),
  success: vi.fn(),
  toastError: vi.fn()
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: actions.success, error: actions.toastError })
}))
vi.mock('@/composables/useProxySettings', () => ({
  useProxySettings: () => {
    const proxies = ref([{
      id: 7,
      proxy_url: 'https://proxy.example:443',
      masked_url: 'https://proxy.example:443',
      priority: 1,
      enabled: true,
      health_status: 'healthy',
      last_check: null,
      response_time_ms: 10,
      consecutive_failures: 0,
      last_error: null,
      total_requests: 1,
      successful_requests: 1,
      failed_requests: 0,
      created_at: null
    }])
    const config = ref({
      enable_proxy: true,
      proxy_health_check_enabled: true,
      proxy_health_check_interval_seconds: 300,
      proxy_max_consecutive_failures: 3,
      fallback_to_direct_connection: true
    })
    return {
      proxies,
      config,
      isLoading: ref(false),
      error: ref(null),
      healthyProxyCount: computed(() => 1),
      degradedProxyCount: computed(() => 0),
      failedProxyCount: computed(() => 0),
      enabledProxyCount: computed(() => 1),
      proxySystemStatus: computed(() => ({ status: 'healthy', message: 'healthy' })),
      fetchProxies: actions.fetchProxies,
      addProxy: actions.addProxy,
      deleteProxy: actions.deleteProxy,
      toggleProxy: actions.toggleProxy,
      testProxy: actions.testProxy,
      updatePriority: actions.updatePriority,
      updateConfig: actions.updateConfig
    }
  }
}))

import ProxySettingsPanel from '@/components/settings/ProxySettingsPanel.vue'

describe('ProxySettingsPanel actions', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses backend toggle state, runs a health test, and saves all config fields', async () => {
    actions.toggleProxy.mockResolvedValue({ success: true, enabled: false, message: 'disabled' })
    actions.testProxy.mockResolvedValue({ health_status: 'healthy' })
    actions.updateConfig.mockResolvedValue({ success: true })

    const wrapper = shallowMount(ProxySettingsPanel)
    await wrapper.get('.toggle-switch input').trigger('change')
    await flushPromises()
    expect(actions.toggleProxy).toHaveBeenCalledWith(7)
    expect(actions.success).toHaveBeenCalledWith('Proxy disabled')

    const testButton = wrapper.findAll('button').find(button => button.text() === 'Test')
    expect(testButton).toBeDefined()
    await testButton!.trigger('click')
    await flushPromises()
    expect(actions.testProxy).toHaveBeenCalledWith(7)

    const saveButton = wrapper.findAll('button').find(button => button.text().includes('Save Config'))
    expect(saveButton).toBeDefined()
    await saveButton!.trigger('click')
    await flushPromises()
    expect(actions.updateConfig).toHaveBeenCalledWith({
      enable_proxy: true,
      proxy_health_check_enabled: true,
      proxy_health_check_interval_seconds: 300,
      proxy_max_consecutive_failures: 3,
      fallback_to_direct_connection: true
    })
    wrapper.unmount()
  })

  it('clears health-test action state and exposes backend errors', async () => {
    actions.testProxy.mockRejectedValue(new Error('Proxy not found'))

    const wrapper = shallowMount(ProxySettingsPanel)
    const testButton = wrapper.findAll('button').find(button => button.text() === 'Test')
    await testButton!.trigger('click')
    await flushPromises()

    expect(actions.toastError).toHaveBeenCalledWith('Proxy not found')
    expect(testButton!.attributes('disabled')).toBeUndefined()
    expect(testButton!.text()).toBe('Test')
    wrapper.unmount()
  })
})
