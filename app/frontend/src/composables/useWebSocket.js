import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket() {
  const messages = ref([])
  const connectionStatus = ref('disconnected')
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`
  let ws = null
  let reconnectTimer = null

  const connect = () => {
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connectionStatus.value = 'connected'
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messages.value.push(data)
        console.log('WebSocket message received:', data)
      } catch (e) {
        console.error('Error parsing WebSocket message:', e)
      }
    }

    ws.onclose = () => {
      connectionStatus.value = 'disconnected'
      console.log('WebSocket disconnected, attempting reconnect...')
      reconnectTimer = setTimeout(connect, 5000)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    if (ws) {
      ws.close()
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }
  })

  return {
    messages,
    connectionStatus
  }
}