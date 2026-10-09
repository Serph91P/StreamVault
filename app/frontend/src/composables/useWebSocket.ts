import { ref, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import router from '@/router'
import { hasRealtimeEventType, normalizeRealtimeEventType, parseRealtimeEvent } from '@/types/events'
import type { RealtimeEvent } from '@/types/events'
import { fetchRealtimeEvents, RealtimeReplayAuthError } from '@/services/realtime'

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
  private hasConnected = false
  private lastEventId = 0
  private terminalAuthFailure = false
  private authRouteBlocked = false
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
      if (import.meta.env.DEV) console.debug('🎭 Mock mode: WebSocket connections disabled')
    }
    
    if (import.meta.env.DEV) console.debug(`WebSocket singleton created with URL: ${this.wsUrl}`)

    window.addEventListener('online', this.handleOnline)
    window.addEventListener('offline', this.handleOffline)
    document.addEventListener('visibilitychange', this.handleVisibilityChange)
    router.afterEach((to) => {
      this.handleRouteChange(to.path)
    })
  }

  private isAuthRoute(path: string): boolean {
    return path.startsWith('/auth/') || path === '/welcome' || path === '/onboarding' || path === '/setup'
  }

  private handleRouteChange(path: string): void {
    this.authRouteBlocked = this.isAuthRoute(path)
    if (this.authRouteBlocked) {
      this.disconnect()
      return
    }

    this.ensureConnected()
  }

  private handleOnline = () => {
    this.isBrowserOnline.value = true
    if (this.connectionStatus.value === 'offline') {
      this.connectionStatus.value = 'disconnected'
    }
    if (!this.terminalAuthFailure) {
      this.ensureConnected()
    }
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
    if (document.visibilityState === 'visible' && !this.terminalAuthFailure) {
      this.ensureConnected()
    }
  }

  public static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager()
      if (import.meta.env.DEV) console.debug('WebSocket singleton instance created')
    } else {
      if (import.meta.env.DEV) console.debug('WebSocket singleton instance reused')
    }
    return WebSocketManager.instance
  }

  public subscribe(callback: () => void) {
    this.subscribers.add(callback)
    
    // 🎭 MOCK MODE: Skip WebSocket connection in mock mode
    const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'
    if (USE_MOCK_DATA) {
      if (import.meta.env.DEV) console.debug('🎭 Mock mode: Skipping WebSocket connection')
      return
    }
    
    // Auto-connect when first subscriber joins
    if (this.subscribers.size === 1) {
      if (import.meta.env.DEV) console.debug('🔌 First subscriber - connecting WebSocket')
      this.connect()
    } else {
      if (import.meta.env.DEV) console.debug(`📡 Additional subscriber (${this.subscribers.size} total) - reusing existing connection`)
    }
  }

  public unsubscribe(callback: () => void) {
    this.subscribers.delete(callback)
    if (import.meta.env.DEV) console.debug(`📡 Subscriber removed (${this.subscribers.size} remaining)`)
    
    // Auto-disconnect when last subscriber leaves
    if (this.subscribers.size === 0) {
      if (import.meta.env.DEV) console.debug('🔌 Last subscriber gone - disconnecting WebSocket')
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
    this.terminalAuthFailure = false
    this.connect()
  }

  public reconnectNow() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.reconnectAttempts = 0
    this.reconnectAttempt.value = 0
    this.terminalAuthFailure = false
    this.connect()
  }

  private connect() {
    if (import.meta.env.VITE_USE_MOCK_DATA === 'true') {
      return
    }

    if (!this.isBrowserOnline.value) {
      this.connectionStatus.value = 'offline'
      return
    }

    // Don't connect on auth/setup routes. The persistent app subscription is
    // already active there, so router.afterEach starts the same singleton as
    // soon as authenticated navigation reaches a protected route.
    const path = window.location.pathname
    if (this.authRouteBlocked || this.isAuthRoute(path)) {
      if (import.meta.env.DEV) console.debug('⏭️ Skipping WebSocket connection on auth page')
      return
    }

    // Prevent multiple connections
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      if (import.meta.env.DEV) console.debug('⚠️ WebSocket already connected or connecting, skipping')
      return
    }

    // Clean up existing connection
    if (this.ws) {
      this.ws.close()
    }

    if (import.meta.env.DEV) console.debug('🔌 Creating single WebSocket connection for entire app')
    this.connectionStatus.value = 'connecting'
    const socket = new WebSocket(this.wsUrl)
    const queuedLiveEvents: RealtimeEvent<string>[] = []
    let isReplaying = false
    this.ws = socket

    socket.onopen = () => {
      if (import.meta.env.DEV) console.debug('WebSocket connected successfully')
      this.reconnectAttempts = 0
      this.reconnectAttempt.value = 0

      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }

      const shouldReplay = this.hasConnected
      this.hasConnected = true
      if (!shouldReplay) {
        this.connectionStatus.value = 'connected'
        return
      }

      isReplaying = true
      void this.replayMissedEvents(socket, this.lastEventId, queuedLiveEvents, () => {
        isReplaying = false
      })
    }

    socket.onmessage = (event) => {
      try {
        const message = parseRealtimeEvent(JSON.parse(event.data))
        if (!message) {
          console.warn('Ignoring invalid WebSocket message:', event.data)
          return
        }

        if (isReplaying) {
          queuedLiveEvents.push(message)
        } else {
          this.dispatchMessage(message)
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    socket.onclose = (event) => {
      if (import.meta.env.DEV) console.debug('🔌 WebSocket disconnected:', event.reason)
      if (this.ws !== socket) {
        return
      }
      this.connectionStatus.value = 'disconnected'
      this.ws = null

      // SECURITY: Don't reconnect on auth failures (code 4001/4003)
      // These indicate the session is invalid/expired - redirect to login
      if (event.code === 4001 || event.code === 4003 || this.terminalAuthFailure) {
        this.handleAuthenticationFailure()
        return
      }

      // Only attempt reconnection if we still have subscribers
      if (this.subscribers.size > 0 && !this.authRouteBlocked) {
        this.attemptReconnect()
      }
    }

    socket.onerror = (error) => {
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
    if (import.meta.env.DEV) console.debug('🔌 WebSocket disconnected')
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
      this.reconnectTimer = window.setTimeout(() => {
        this.reconnectTimer = null
        if (this.subscribers.size > 0) {
          if (import.meta.env.DEV) console.debug('🔄 Resetting retry counter after cooldown period')
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
    
    if (import.meta.env.DEV) console.debug(`🔄 Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      if (this.subscribers.size > 0) {
        this.connect()
      }
    }, delay)
  }

  private async replayMissedEvents(
    socket: WebSocket,
    since: number,
    queuedLiveEvents: RealtimeEvent<string>[],
    finishReplay: () => void
  ) {
    try {
      const replay = await fetchRealtimeEvents(since)
      if (this.ws !== socket || socket.readyState !== WebSocket.OPEN) {
        return
      }

      if (replay.gap) {
        console.warn(`Realtime replay retention gap after event ${since}; applying retained events`)
      }
      replay.events.forEach((message) => this.dispatchMessage(message))
      finishReplay()
      queuedLiveEvents.forEach((message) => this.dispatchMessage(message))
      this.connectionStatus.value = 'connected'
    } catch (error) {
      if (this.ws !== socket) {
        return
      }
      if (error instanceof RealtimeReplayAuthError) {
        this.terminalAuthFailure = true
        this.handleAuthenticationFailure()
        socket.close()
        return
      }

      console.error('Failed to replay realtime events:', error)
      finishReplay()
      queuedLiveEvents.forEach((message) => this.dispatchMessage(message))
      this.connectionStatus.value = 'connected'
    }
  }

  private handleAuthenticationFailure() {
    this.terminalAuthFailure = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
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
  }

  private dispatchMessage(message: RealtimeEvent<string>) {
    if (this.isDuplicateMessage(message)) {
      if (import.meta.env.DEV) console.debug(`Skipping duplicate WebSocket event: ${message.type}`)
      return
    }

    if (typeof message.event_id === 'number' && Number.isFinite(message.event_id)) {
      this.lastEventId = Math.max(this.lastEventId, message.event_id)
    }
    this.messages.value.push(message)

    // Store connection ID from server for debugging
    if (hasRealtimeEventType(message, 'connection.status') && message.data?.connection_id) {
      this.connectionId = message.data.connection_id
      const realIp = message.data.real_ip
      const isProxied = message.data.is_reverse_proxied
      const proxyInfo = isProxied ? ' (via reverse proxy)' : ''
      if (import.meta.env.DEV) console.debug(`🆔 WebSocket connection ID: ${this.connectionId} - Real IP: ${realIp}${proxyInfo}`)
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

    const normalizedType = normalizeRealtimeEventType(message.type)

    if (eventId) {
      return `${normalizedType}:${eventId}`
    }

    const timestamp = firstString(message.timestamp, data.timestamp, data.created_at)
    if (!timestamp) {
      return null
    }

    return [
      normalizedType,
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
    if (import.meta.env.DEV) console.debug(`📱 Component ${componentId} subscribing to WebSocket`)
    manager.subscribe(componentCallback)
  })
  
  onUnmounted(() => {
    if (import.meta.env.DEV) console.debug(`📱 Component ${componentId} unsubscribing from WebSocket`)
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
