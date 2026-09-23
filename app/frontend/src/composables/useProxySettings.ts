import { ref, computed, onMounted, onUnmounted } from 'vue'
import type {
  ProxySettings,
  ProxyAddRequest,
  ProxyConfigSettings,
  ProxyHealthUpdateEvent
} from '@/types/proxy'
import { proxyApi } from '@/services/api'
import { hasRealtimeEventType } from '@/types/events'
import { WebSocketManager, useWebSocket } from '@/composables/useWebSocket'

/**
 * State and backend integration for multi-proxy management.
 * Realtime health updates share the application-wide WebSocket owner.
 */
export function useProxySettings() {
  const proxies = ref<ProxySettings[]>([])
  const config = ref<ProxyConfigSettings>({
    enable_proxy: true,
    proxy_health_check_enabled: true,
    proxy_health_check_interval_seconds: 300,
    proxy_max_consecutive_failures: 3,
    fallback_to_direct_connection: true
  })
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  useWebSocket()
  const websocketManager = WebSocketManager.getInstance()
  let stopListeningForRealtimeEvents: (() => void) | null = null

  const healthyProxyCount = computed(() =>
    proxies.value.filter(proxy => proxy.enabled && proxy.health_status === 'healthy').length
  )
  const degradedProxyCount = computed(() =>
    proxies.value.filter(proxy => proxy.enabled && proxy.health_status === 'degraded').length
  )
  const failedProxyCount = computed(() =>
    proxies.value.filter(proxy => proxy.enabled && proxy.health_status === 'failed').length
  )
  const enabledProxyCount = computed(() => proxies.value.filter(proxy => proxy.enabled).length)

  const proxySystemStatus = computed(() => {
    if (!config.value.enable_proxy) {
      return { status: 'disabled', message: 'Proxy system disabled' }
    }
    if (proxies.value.length === 0) {
      return { status: 'no-proxies', message: 'No proxies configured' }
    }
    if (healthyProxyCount.value > 0) {
      return { status: 'healthy', message: `${healthyProxyCount.value} healthy proxy(ies) available` }
    }
    if (degradedProxyCount.value > 0) {
      return { status: 'degraded', message: `${degradedProxyCount.value} degraded proxy(ies) - may be slow` }
    }
    if (config.value.fallback_to_direct_connection) {
      return { status: 'fallback', message: 'All proxies failed - using direct connection' }
    }
    return { status: 'critical', message: 'All proxies failed - recordings will fail!' }
  })

  async function fetchProxies() {
    isLoading.value = true
    error.value = null
    try {
      const response = await proxyApi.getAll()
      proxies.value = response.proxies
      config.value = response.system_config
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Failed to fetch proxies'
      console.error('Failed to fetch proxies:', caught)
    } finally {
      isLoading.value = false
    }
  }

  async function addProxy(request: ProxyAddRequest) {
    const result = await proxyApi.add(request)
    await fetchProxies()
    return result
  }

  async function deleteProxy(id: number, maskedUrl: string) {
    if (!confirm(`Delete proxy ${maskedUrl}?\n\nThis will remove the proxy from the rotation.`)) {
      return false
    }
    await proxyApi.delete(id)
    await fetchProxies()
    return true
  }

  async function toggleProxy(id: number) {
    const result = await proxyApi.toggle(id)
    const proxy = proxies.value.find(candidate => candidate.id === id)
    if (proxy) proxy.enabled = result.enabled
    return result
  }

  async function testProxy(id: number) {
    const response = await proxyApi.test(id)
    const result = response.result
    const proxy = proxies.value.find(candidate => candidate.id === id)
    if (proxy) {
      proxy.health_status = result.health_status
      proxy.response_time_ms = result.response_time_ms
      proxy.consecutive_failures = result.consecutive_failures
      proxy.enabled = result.enabled
      proxy.last_error = result.error
    }
    return result
  }

  async function updatePriority(id: number, priority: number) {
    await proxyApi.updatePriority(id, priority)
    await fetchProxies()
  }

  async function getBestProxy() {
    return proxyApi.getBest()
  }

  async function updateConfig(newConfig: Partial<ProxyConfigSettings>) {
    const result = await proxyApi.updateConfig(newConfig)
    config.value = result.config
    return result
  }

  function handleProxyHealthUpdate(data: ProxyHealthUpdateEvent['data']) {
    const proxy = proxies.value.find(candidate => candidate.id === data.proxy_id)
    if (proxy) {
      proxy.health_status = data.health_status
      proxy.response_time_ms = data.response_time_ms
      proxy.last_error = data.last_error
      proxy.consecutive_failures = data.consecutive_failures
      proxy.last_check = data.checked_at
      console.log(`🔄 Proxy #${data.proxy_id} health updated: ${data.health_status}`)
    }
  }

  onMounted(() => {
    void fetchProxies()
    stopListeningForRealtimeEvents = websocketManager.onMessage((message) => {
      if (hasRealtimeEventType(message, 'proxy_health_update')) {
        handleProxyHealthUpdate(message.data as ProxyHealthUpdateEvent['data'])
      }
    })
  })

  onUnmounted(() => {
    stopListeningForRealtimeEvents?.()
    stopListeningForRealtimeEvents = null
  })

  return {
    proxies,
    config,
    isLoading,
    error,
    healthyProxyCount,
    degradedProxyCount,
    failedProxyCount,
    enabledProxyCount,
    proxySystemStatus,
    fetchProxies,
    addProxy,
    deleteProxy,
    toggleProxy,
    testProxy,
    updatePriority,
    getBestProxy,
    updateConfig
  }
}
