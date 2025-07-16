import { ref, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'

interface WebSocketMessage {
  type: string
  data?: any
  message?: string
}

// Singleton WebSocket Manager - ONE connection for the entire app
class WebSocketManager {
  private static instance: WebSocketManager | null = null
  private ws: WebSocket | null = null
  private reconnectTimer: number | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private wsUrl: string
  
  // Reactive state shared across all components
  public messages: Ref<WebSocketMessage[]> = ref([])
  public connectionStatus = ref('disconnected')
  private subscribers: Set<() => void> = new Set()

  private constructor() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.wsUrl = `${wsProtocol}//${window.location.host}/ws`
  }

  public static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager()
    }
    return WebSocketManager.instance
  }

  public subscribe(callback: () => void) {
    this.subscribers.add(callback)
    
    // Auto-connect when first subscriber joins
    if (this.subscribers.size === 1) {
      console.log('🔌 First subscriber - connecting WebSocket')
      this.connect()
    } else {
      console.log(`📡 Additional subscriber (${this.subscribers.size} total) - reusing existing connection`)
    }
  }

  public unsubscribe(callback: () => void) {
    this.subscribers.delete(callback)
    console.log(`📡 Subscriber removed (${this.subscribers.size} remaining)`)
    
    // Auto-disconnect when last subscriber leaves
    if (this.subscribers.size === 0) {
      console.log('🔌 Last subscriber gone - disconnecting WebSocket')
      this.disconnect()
    }
  }

  private connect() {
    // Prevent multiple connections
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('⚠️ WebSocket already connected, skipping')
      return
    }
    
    // Clean up existing connection
    if (this.ws) {
      this.ws.close()
    }
    
    console.log('🔌 Creating single WebSocket connection for entire app')
    this.connectionStatus.value = 'connecting'
    this.ws = new WebSocket(this.wsUrl)

    this.ws.onopen = () => {
      console.log('✅ WebSocket connected successfully')
      this.connectionStatus.value = 'connected'
      this.reconnectAttempts = 0
      
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        this.messages.value.push(message)
        
        // Keep only last 100 messages to prevent memory leaks
        if (this.messages.value.length > 100) {
          this.messages.value = this.messages.value.slice(-100)
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    this.ws.onclose = (event) => {
      console.log('🔌 WebSocket disconnected:', event.reason)
      this.connectionStatus.value = 'disconnected'
      this.ws = null
      
      // Only attempt reconnection if we still have subscribers
      if (this.subscribers.size > 0) {
        this.attemptReconnect()
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.connectionStatus.value = 'error'
    }
  }

  private disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    
    this.connectionStatus.value = 'disconnected'
    console.log('🔌 WebSocket disconnected')
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ Max reconnection attempts reached')
      this.connectionStatus.value = 'failed'
      return
    }
    
    this.reconnectAttempts++
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000)
    
    console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    this.reconnectTimer = window.setTimeout(() => {
      if (this.subscribers.size > 0) {
        this.connect()
      }
    }, delay)
  }
}

// Export the composable function that uses the singleton
export function useWebSocket() {
  const manager = WebSocketManager.getInstance()
  
  // Create a unique callback for this component instance
  const componentCallback = () => {
    // This callback is used for subscriber tracking
    // The actual reactivity is handled by the shared refs
  }
  
  onMounted(() => {
    manager.subscribe(componentCallback)
  })
  
  onUnmounted(() => {
    manager.unsubscribe(componentCallback)
  })
  
  return {
    messages: manager.messages,
    connectionStatus: manager.connectionStatus
  }
}
