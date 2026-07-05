import { ref, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import { logDebug, logWebSocket } from '@/utils/logger'
import router from '@/router'
import { hasRealtimeEventType, parseRealtimeEvent } from '@/types/events'
import type { RealtimeEvent } from '@/types/events'

type ConnectionStatus = 'auth_failed' | 'connected' | 'connecting' | 'disconnected' | 'error' | 'failed' | 'offline' | 'reconnecting'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return String(value)
    }
  }
}

// Singleton WebSocket Manager - ONE connection for the entire app
export class WebSocketManager {
  private static instance: WebSocketManager | null = null
  private ws: WebSocket | null = null
  private reconnectTimer: number | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private wsUrl: string
  private connectionId: string | null = null
  private isRedirecting = false
  private recentEventKeys = new Map<string, number>()
  private readonly dedupeWindowMs = 5000
  private readonly maxRecentEventKeys = 200
  
  // Reactive state shared across all components
  public messages: Ref<RealtimeEvent<string>[]> = ref([])
  public connectionStatus = ref<ConnectionStatus>('disconnected')
  public isBrowserOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
  public reconnectAttempt = ref(0)
  public maxReconnectAttemptCount = this.maxReconnectAttempts
  private subscribers: Set<() => void> = new Set()
  private messageListeners: Set<(event: RealtimeEvent<string>) => void> = new Set()

  private constructor() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.wsUrl = `${wsProtocol}//${window.location.host}/ws`
    
    // 🎭 MOCK MODE: Check if using mock data
    const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'
    if (USE_MOCK_DATA) {
      console.log('🎭 Mock mode: WebSocket connections disabled')
    }
    
    logDebug('WebSocketManager', `Singleton created with URL: ${this.wsUrl}`)

    window.addEventListener('online', this.handleOnline)
    window.addEventListener('offline', this.handleOffline)
    document.addEventListener('visibilitychange', this.handleVisibilityChange)
  }

  private handleOnline = () => {
    this.isBrowserOnline.value = true
    if (this.connectionStatus.value === 'offline') {
      this.connectionStatus.value = 'disconnected'
    }
    this.ensureConnected()
  }

  private handleOffline = () => {
    this.isBrowserOnline.value = false
    this.connectionStatus.value = 'offline'
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private handleVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
      this.ensureConnected()
    }
  }

  public static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager()
      logDebug('WebSocketManager', 'Singleton instance created')
    } else {
      logDebug('WebSocketManager', 'Singleton instance reused')
    }
    return WebSocketManager.instance
  }

  public subscribe(callback: () => void) {
    this.subscribers.add(callback)
    
    // 🎭 MOCK MODE: Skip WebSocket connection in mock mode
    const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'
    if (USE_MOCK_DATA) {
      console.log('🎭 Mock mode: Skipping WebSocket connection')
      return
    }
    
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

  public onMessage(callback: (event: RealtimeEvent<string>) => void): () => void {
    this.messageListeners.add(callback)
    return () => {
      this.messageListeners.delete(callback)
    }
  }

  /**
   * Public connect entrypoint. Safe to call multiple times. No-op if already
   * open/connecting. Used by useAuth.login() to eliminate the race where the
   * WebSocket would otherwise stay disconnected until the next component mount.
   */
  public ensureConnected() {
    if (this.subscribers.size === 0) {
      // No active subscriber yet, the next subscribe() will connect for us.
      return
    }
    this.connect()
  }

  public reconnectNow() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.reconnectAttempts = 0
    this.reconnectAttempt.value = 0
    this.connect()
  }

  private connect() {
    if (!this.isBrowserOnline.value) {
      this.connectionStatus.value = 'offline'
      return
    }

    // Don't connect on auth pages - there's no valid session
    const path = window.location.pathname
    if (path.startsWith('/auth/')) {
      console.log('⏭️ Skipping WebSocket connection on auth page')
      return
    }

    // Prevent multiple connections
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      console.log('⚠️ WebSocket already connected or connecting, skipping')
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
      logWebSocket('WebSocketManager', 'connected', 'WebSocket connected successfully')
      this.connectionStatus.value = 'connected'
      this.reconnectAttempts = 0
      this.reconnectAttempt.value = 0
      
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
    }

    this.ws.onmessage = (event) => {
      try {
        const message = parseRealtimeEvent(JSON.parse(event.data))
        if (!message) {
          console.warn('Ignoring invalid WebSocket message:', event.data)
          return
        }

        if (this.isDuplicateMessage(message)) {
          logDebug('WebSocketManager', `Skipping duplicate WebSocket event: ${message.type}`)
          return
        }

        this.messages.value.push(message)
        
        // Store connection ID from server for debugging
        if (hasRealtimeEventType(message, 'connection.status') && message.data?.connection_id) {
          this.connectionId = message.data.connection_id
          const realIp = message.data.real_ip
          const isProxied = message.data.is_reverse_proxied
          const proxyInfo = isProxied ? ' (via reverse proxy)' : ''
          console.log(`🆔 WebSocket connection ID: ${this.connectionId} - Real IP: ${realIp}${proxyInfo}`)
        }
        
        // Keep only last 100 messages to prevent memory leaks
        if (this.messages.value.length > 100) {
          this.messages.value = this.messages.value.slice(-100)
        }

        this.messageListeners.forEach((listener) => {
          try {
            listener(message)
          } catch (listenerError) {
            console.error('Error in WebSocket message listener:', listenerError)
          }
        })
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    this.ws.onclose = (event) => {
      console.log('🔌 WebSocket disconnected:', event.reason)
      this.connectionStatus.value = 'disconnected'
      this.ws = null
      
      // SECURITY: Don't reconnect on auth failures (code 4001/4003)
      // These indicate the session is invalid/expired - redirect to login
      if (event.code === 4001 || event.code === 4003) {
        console.warn('🔒 WebSocket auth failed - session invalid or expired')
        this.connectionStatus.value = 'auth_failed'
        // Use Vue Router (soft navigation) instead of window.location.href
        // to prevent full page reload → reconnect → auth fail → reload loop
        if (!this.isRedirecting) {
          this.isRedirecting = true
          router.push('/auth/login').finally(() => {
            this.isRedirecting = false
          })
        }
        return
      }
      
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
    if (!this.isBrowserOnline.value) {
      this.connectionStatus.value = 'offline'
      return
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ Max reconnection attempts reached')
      this.connectionStatus.value = 'failed'
      
      // After failure, wait 60 seconds and reset retry counter for fresh attempt
      setTimeout(() => {
        if (this.subscribers.size > 0) {
          console.log('🔄 Resetting retry counter after cooldown period')
          this.reconnectAttempts = 0
          this.reconnectAttempt.value = 0
          this.connectionStatus.value = 'disconnected'
          this.attemptReconnect()
        }
      }, 60000)
      return
    }
    
    this.reconnectAttempts++
    this.reconnectAttempt.value = this.reconnectAttempts
    this.connectionStatus.value = 'reconnecting'
    // Exponential backoff with jitter to prevent thundering herd
    const baseDelay = 1000 * Math.pow(2, this.reconnectAttempts - 1)
    const jitter = Math.random() * 0.3 * baseDelay  // Add 0-30% jitter
    const delay = Math.min(baseDelay + jitter, 30000)
    
    console.log(`🔄 Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    this.reconnectTimer = window.setTimeout(() => {
      if (this.subscribers.size > 0) {
        this.connect()
      }
    }, delay)
  }

  private getMessageDedupeKey(message: RealtimeEvent<string>): string | null {
    const data = asRecord(message.data)
    const eventId = firstString(
      message.event_id,
      message.dedupe_key,
      message.id,
      data.event_id,
      data.dedupe_key,
      data.dedupeKey,
      data.id,
      data.test_id
    )

    if (eventId) {
      return `${message.type}:${eventId}`
    }

    const timestamp = firstString(message.timestamp, data.timestamp, data.created_at)
    if (!timestamp) {
      return null
    }

    return [
      message.type,
      firstString(data.streamer_id, data.streamerId, data.streamer_name, data.username),
      firstString(data.recording_id, data.recordingId, data.video_id, data.videoId),
      firstString(data.task_id, data.taskId),
      timestamp
    ].filter(Boolean).join(':')
  }

  private isDuplicateMessage(message: RealtimeEvent<string>): boolean {
    const key = this.getMessageDedupeKey(message)
    if (!key) {
      return false
    }

    const now = Date.now()
    const lastSeen = this.recentEventKeys.get(key)
    this.recentEventKeys.set(key, now)

    for (const [recentKey, seenAt] of this.recentEventKeys) {
      if (now - seenAt > this.dedupeWindowMs || this.recentEventKeys.size > this.maxRecentEventKeys) {
        this.recentEventKeys.delete(recentKey)
      }
    }

    return lastSeen !== undefined && now - lastSeen < this.dedupeWindowMs
  }
}

// Export the composable function that uses the singleton
export function useWebSocket() {
  const manager = WebSocketManager.getInstance()
  
  // Create a unique callback for this component instance
  const componentId = Math.random().toString(36).substr(2, 9)
  const componentCallback = () => {
    // This callback is used for subscriber tracking
    // The actual reactivity is handled by the shared refs
  }
  
  onMounted(() => {
    console.log(`📱 Component ${componentId} subscribing to WebSocket`)
    manager.subscribe(componentCallback)
  })
  
  onUnmounted(() => {
    console.log(`📱 Component ${componentId} unsubscribing from WebSocket`)
    manager.unsubscribe(componentCallback)
  })
  
  return {
    messages: manager.messages,
    connectionStatus: manager.connectionStatus,
    isBrowserOnline: manager.isBrowserOnline,
    reconnectAttempt: manager.reconnectAttempt,
    maxReconnectAttempts: manager.maxReconnectAttemptCount,
    reconnectNow: () => manager.reconnectNow()
  }
}
