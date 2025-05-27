import { ref, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'

interface WebSocketMessage {
  type: string
  data?: any
  message?: string
}

export function useWebSocket() {
  const messages: Ref<WebSocketMessage[]> = ref([])
  const connectionStatus = ref('disconnected')
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`
  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null

  const connect = () => {
    // Prevent multiple connections
    if (ws && ws.readyState === WebSocket.OPEN) {
      console.log('🔌 WebSocket already connected, skipping...')
      return
    }
    
    // Clean up existing connection
    if (ws) {
      ws.close()
    }
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connectionStatus.value = 'connected'
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('🔌 WebSocket raw message received:', event.data)
        console.log('🔌 WebSocket parsed message:', data)
        
        // Accept all notification types including test notifications from settings.py
        if (data && (
          data.type === 'stream.online' || 
          data.type === 'stream.offline' || 
          data.type === 'channel.update' ||
          data.type === 'stream.update' ||
          data.type === 'recording.started' ||
          data.type === 'recording.completed' ||
          data.type === 'recording.failed' ||
          data.type === 'test'
          // Removed 'connection.status' to prevent spam notifications
        )) {
          console.log('✅ Message type accepted:', data.type)
          console.log('📨 Adding message to messages array:', data)
          console.log('📊 Messages array before push:', messages.value.length)
          
          // Create a new array reference to trigger reactivity
          const newMessages = [...messages.value, data]
          messages.value = newMessages
          
          console.log('📊 Messages array after push:', messages.value.length)
          console.log('📋 Current messages array:', messages.value)
          console.log('🎯 Latest message:', messages.value[messages.value.length - 1])
        } else {
          console.warn('❌ Message type not recognized or data invalid:', data?.type, 'Full data:', data)
        }
      } catch (e) {
        console.error('💥 Error parsing WebSocket message:', e)
      }
    }

    ws.onclose = () => {
      connectionStatus.value = 'disconnected'
      console.log('WebSocket disconnected, attempting reconnect...')
      
      // Clear existing timer
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      
      // Only reconnect if we're not unmounting
      reconnectTimer = window.setTimeout(() => {
        if (connectionStatus.value === 'disconnected') {
          connect()
        }
      }, 5000)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    connectionStatus.value = 'disconnected'
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
  })

  return {
    messages,
    connectionStatus
  }
}