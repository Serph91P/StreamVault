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

  const handlers = new Map<string, Set<{ handler: EventHandler }>>()

  function onEvent(type: string, handler: EventHandler): () => void {
    type = normalizeRealtimeEventType(type)
    if (!handlers.has(type)) {
      handlers.set(type, new Set())
    }

    // Each subscription owns its entry, even when aliases share a callback.
    const registration = { handler }
    handlers.get(type)!.add(registration)
    return () => {
      handlers.get(type)?.delete(registration)
      if (handlers.get(type)?.size === 0) handlers.delete(type)
    }
  }

  function onEvents(types: string[], handler: EventHandler): () => void {
    const unsubs = types.map((type) => onEvent(type, handler))
    return () => unsubs.forEach((fn) => fn())
  }

  function dispatchEvent(event: RealtimeEvent<string>) {
    if (!event?.type) return

    const callbacks = new Set<EventHandler>()
    handlers.get(normalizeRealtimeEventType(event.type))?.forEach(({ handler }) => callbacks.add(handler))

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
