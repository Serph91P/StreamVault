import { ref, computed, onMounted, onUnmounted } from 'vue'
import type {
  ProxySettings,
  ProxyAddRequest,
  ProxyListResponse,
  ProxyConfigSettings,
  ProxyHealthCheckResult,
  BestProxyResponse,
  ProxyHealthUpdateEvent
} from '@/types/proxy'
import { mockProxies } from '@/mocks/mockData'
import { hasRealtimeEventType } from '@/types/events'
import { WebSocketManager, useWebSocket } from '@/composables/useWebSocket'

// Check for mock data mode
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'

/**
 * Composable for Multi-Proxy System Management
 * 
 * Provides state management and API methods for proxy management
 * with real-time WebSocket updates for health status changes.
 */
export function useProxySettings() {
  // State
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

  // Reuse the application-wide realtime connection and its lifecycle ownership.
  useWebSocket()
  const websocketManager = WebSocketManager.getInstance()
  let stopListeningForRealtimeEvents: (() => void) | null = null

  // Computed properties
  const healthyProxyCount = computed(() => {
    return proxies.value.filter(p => p.enabled && p.health_status === 'healthy').length
  })

  const degradedProxyCount = computed(() => {
    return proxies.value.filter(p => p.enabled && p.health_status === 'degraded').length
  })

  const failedProxyCount = computed(() => {
    return proxies.value.filter(p => p.enabled && p.health_status === 'failed').length
  })

  const enabledProxyCount = computed(() => {
    return proxies.value.filter(p => p.enabled).length
  })

  const proxySystemStatus = computed(() => {
    if (!config.value.enable_proxy) {
      return { status: 'disabled', message: 'Proxy system disabled' }
    }

    if (proxies.value.length === 0) {
      return { status: 'no-proxies', message: 'No proxies configured' }
    }

    if (healthyProxyCount.value > 0) {
      return { 
        status: 'healthy', 
        message: `${healthyProxyCount.value} healthy proxy(ies) available` 
      }
    }

    if (degradedProxyCount.value > 0) {
      return { 
        status: 'degraded', 
        message: `${degradedProxyCount.value} degraded proxy(ies) - may be slow` 
      }
    }

    if (config.value.fallback_to_direct_connection) {
      return { 
        status: 'fallback', 
        message: 'All proxies failed - using direct connection' 
      }
    }

    return { 
      status: 'critical', 
      message: 'All proxies failed - recordings will fail!' 
    }
  })

  // API Methods
  async function fetchProxies() {
    isLoading.value = true
    error.value = null

    // Use mock data in development mode
    if (USE_MOCK_DATA) {
      proxies.value = mockProxies as ProxySettings[]
      isLoading.value = false
      return
    }

    try {
      const response = await fetch('/api/proxy/list', {
        credentials: 'include'  // CRITICAL for session
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      // Handle JSON parse errors gracefully
      let data: ProxyListResponse
      try {
        const text = await response.text()
        data = text ? JSON.parse(text) : { proxies: [], system_config: config.value }
      } catch (parseError) {
        console.warn('Failed to parse proxy response as JSON:', parseError)
        proxies.value = []
        return
      }
      
      proxies.value = data.proxies || []
      config.value = data.system_config
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch proxies'
      console.error('Failed to fetch proxies:', e)
    } finally {
      isLoading.value = false
    }
  }

  async function addProxy(request: ProxyAddRequest) {
    const response = await fetch('/api/proxy/add', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to add proxy')
    }

    const result = await response.json()
    
    // Refresh list to get updated health status
    await fetchProxies()
    
    return result
  }

  async function deleteProxy(id: number, maskedUrl: string) {
    // ALWAYS confirm destructive actions
    if (!confirm(`Delete proxy ${maskedUrl}?\n\nThis will remove the proxy from the rotation.`)) {
      return false
    }

    const response = await fetch(`/api/proxy/${id}`, {
      method: 'DELETE',
      credentials: 'include'
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to delete proxy')
    }

    await fetchProxies()  // Refresh list
    return true
  }

  async function toggleProxy(id: number, enabled: boolean) {
    const response = await fetch(`/api/proxy/${id}/toggle`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to toggle proxy')
    }

    await fetchProxies()  // Refresh list
  }

  async function testProxy(id: number) {
    const response = await fetch(`/api/proxy/${id}/test`, {
      method: 'POST',
      credentials: 'include'
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to test proxy')
    }

    const result: ProxyHealthCheckResult = await response.json()
    
    // Update local state
    const proxy = proxies.value.find(p => p.id === id)
    if (proxy) {
      proxy.health_status = result.health_status
      proxy.response_time_ms = result.response_time_ms
      proxy.last_error = result.error
      proxy.last_check = result.checked_at
    }

    return result
  }

  async function updatePriority(id: number, priority: number) {
    const response = await fetch(`/api/proxy/${id}/update-priority`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ priority })
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to update priority')
    }

    await fetchProxies()  // Refresh list to show new order
  }

  async function getBestProxy() {
    const response = await fetch('/api/proxy/best', {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error('Failed to get best proxy')
    }

    const result: BestProxyResponse = await response.json()
    return result
  }

  async function updateConfig(newConfig: Partial<ProxyConfigSettings>) {
    const response = await fetch('/api/proxy/config/update', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig)
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to update configuration')
    }

    const result = await response.json()
    config.value = result.config
    return result
  }


  function handleProxyHealthUpdate(data: ProxyHealthUpdateEvent['data']) {
    const proxy = proxies.value.find(p => p.id === data.proxy_id)
    if (proxy) {
      proxy.health_status = data.health_status
      proxy.response_time_ms = data.response_time_ms
      proxy.last_error = data.last_error
      proxy.consecutive_failures = data.consecutive_failures
      proxy.last_check = data.checked_at
      
      console.log(`🔄 Proxy #${data.proxy_id} health updated: ${data.health_status}`)
    }
  }

  // Lifecycle
  onMounted(() => {
    fetchProxies()
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
    // State
    proxies,
    config,
    isLoading,
    error,

    // Computed
    healthyProxyCount,
    degradedProxyCount,
    failedProxyCount,
    enabledProxyCount,
    proxySystemStatus,

    // Methods
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
