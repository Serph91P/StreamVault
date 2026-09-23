import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProxySettings } from '@/types/proxy'

const api = vi.hoisted(() => ({
  getAll: vi.fn(),
  add: vi.fn(),
  delete: vi.fn(),
  toggle: vi.fn(),
  test: vi.fn(),
  updatePriority: vi.fn(),
  updateConfig: vi.fn(),
  getBest: vi.fn()
}))
const onMessage = vi.hoisted(() => vi.fn(() => vi.fn()))

vi.mock('@/services/api', () => ({ proxyApi: api }))
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: vi.fn(),
  WebSocketManager: { getInstance: () => ({ onMessage }) }
}))

import { useProxySettings } from '@/composables/useProxySettings'

const proxy: ProxySettings = {
  id: 7,
  proxy_url: 'https://proxy.example:443',
  masked_url: 'https://proxy.example:443',
  priority: 1,
  enabled: true,
  health_status: 'unknown',
  last_check: null,
  response_time_ms: null,
  consecutive_failures: 0,
  last_error: null,
  total_requests: 0,
  successful_requests: 0,
  failed_requests: 0,
  created_at: null
}
const systemConfig = {
  enable_proxy: true,
  proxy_health_check_enabled: true,
  proxy_health_check_interval_seconds: 300,
  proxy_max_consecutive_failures: 3,
  fallback_to_direct_connection: true
}

function mountComposable() {
  let state!: ReturnType<typeof useProxySettings>
  const Harness = defineComponent({
    setup() {
      state = useProxySettings()
      return () => h('div')
    }
  })
  const wrapper = mount(Harness)
  return { wrapper, get state() { return state } }
}

describe('useProxySettings backend reconciliation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getAll.mockResolvedValue({ proxies: [{ ...proxy }], system_config: { ...systemConfig } })
  })

  it('loads exact list/config envelopes and reconciles toggle, nested health and config responses', async () => {
    api.toggle.mockResolvedValue({ success: true, enabled: false, message: 'disabled' })
    api.test.mockResolvedValue({
      success: true,
      result: {
        proxy_id: 7,
        health_status: 'degraded',
        response_time_ms: 456,
        consecutive_failures: 2,
        enabled: true,
        error: 'slow'
      }
    })
    api.updateConfig.mockResolvedValue({
      success: true,
      message: 'updated',
      config: { ...systemConfig, proxy_max_consecutive_failures: 6 }
    })

    const harness = mountComposable()
    await flushPromises()
    expect(harness.state.proxies.value).toEqual([{ ...proxy }])
    expect(harness.state.config.value).toEqual(systemConfig)

    await harness.state.toggleProxy(7)
    expect(api.toggle).toHaveBeenCalledWith(7)
    expect(harness.state.proxies.value[0].enabled).toBe(false)

    await expect(harness.state.testProxy(7)).resolves.toMatchObject({ health_status: 'degraded' })
    expect(harness.state.proxies.value[0]).toMatchObject({
      health_status: 'degraded',
      response_time_ms: 456,
      consecutive_failures: 2,
      enabled: true,
      last_error: 'slow',
      last_check: null
    })

    await harness.state.updateConfig({ proxy_max_consecutive_failures: 6 })
    expect(harness.state.config.value.proxy_max_consecutive_failures).toBe(6)
    harness.wrapper.unmount()
    expect(onMessage.mock.results[0].value).toHaveBeenCalledOnce()
  })

  it('clears loading deterministically and exposes a failed list message', async () => {
    api.getAll.mockRejectedValueOnce(new Error('Proxy list unavailable'))
    const harness = mountComposable()
    await flushPromises()
    expect(harness.state.isLoading.value).toBe(false)
    expect(harness.state.error.value).toBe('Proxy list unavailable')
    harness.wrapper.unmount()
  })
})
