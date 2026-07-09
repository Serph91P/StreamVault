import { defineStore } from 'pinia'
import { computed } from 'vue'
import { WebSocketManager } from '@/composables/useWebSocket'
import { normalizeRealtimeEventType } from '@/types/events'
import type { RealtimeEvent } from '@/types/events'

type EventHandler = (event: RealtimeEvent<string>) => void

export const useRealtimeStore = defineStore('realtime', () => {
  const manager = WebSocketManager.getInstance()

  // Permanent subscription so WebSocket stays connected as long as the app lives.
  // The store is created once by Pinia during normal app lifetime.
  manager.subscribe(() => {})

  const connectionStatus = computed(() => manager.connectionStatus.value)
  const recentEvents = computed(() => manager.messages.value)
  const isBrowserOnline = computed(() => manager.isBrowserOnline.value)
  const reconnectAttempt = computed(() => manager.reconnectAttempt.value)
  const maxReconnectAttempts = computed(() => manager.maxReconnectAttemptCount)
  const isReconnecting = computed(() => reconnectAttempt.value > 0 && connectionStatus.value !== 'connected')

  const handlers = new Map<string, Set<EventHandler>>()

  function onEvent(type: string, handler: EventHandler): () => void {
    if (!handlers.has(type)) {
      handlers.set(type, new Set())
    }

    handlers.get(type)!.add(handler)
    return () => {
      handlers.get(type)?.delete(handler)
    }
  }

  function onEvents(types: string[], handler: EventHandler): () => void {
    const unsubs = types.map((type) => onEvent(type, handler))
    return () => unsubs.forEach((fn) => fn())
  }

  function dispatchEvent(event: RealtimeEvent<string>) {
    if (!event?.type) return

    const callbacks = new Set<EventHandler>()
    handlers.get(event.type)?.forEach((handler) => callbacks.add(handler))

    const normalizedType = normalizeRealtimeEventType(event.type)
    if (normalizedType !== event.type) {
      handlers.get(normalizedType)?.forEach((handler) => callbacks.add(handler))
    }

    callbacks.forEach((handler) => handler(event))
  }

  manager.onMessage(dispatchEvent)

  return {
    connectionStatus,
    recentEvents,
    isBrowserOnline,
    reconnectAttempt,
    maxReconnectAttempts,
    isReconnecting,
    onEvent,
    onEvents,
    reconnectNow: () => manager.reconnectNow()
  }
})
