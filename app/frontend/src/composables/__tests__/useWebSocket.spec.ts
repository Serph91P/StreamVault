import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/router', () => ({
  default: {
    push: vi.fn(() => Promise.resolve())
  }
}))

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: FakeWebSocket[] = []

  readonly url: string
  readyState = FakeWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null

  constructor(url: string | URL) {
    this.url = String(url)
    FakeWebSocket.instances.push(this)
  }

  open() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  message(payload: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }))
  }

  close() {
    if (this.readyState === FakeWebSocket.CLOSED) return
    this.serverClose(1000, 'client closed')
  }

  serverClose(code = 1006, reason = 'connection lost') {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.({ code, reason } as CloseEvent)
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body)
  } as Response
}

describe('realtime WebSocket lifecycle authority', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useFakeTimers()
    vi.spyOn(Math, 'random').mockReturnValue(0)
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ proxies: [], system_config: {} })))
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shares one socket between the shell and proxy settings and owns all teardown', async () => {
    const { useWebSocket } = await import('../useWebSocket')
    const { useProxySettings } = await import('../useProxySettings')
    const Harness = defineComponent({
      setup() {
        useWebSocket()
        useProxySettings()
        return () => h('div')
      }
    })

    const wrapper = mount(Harness)
    await flushPromises()

    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(FakeWebSocket.instances[0].readyState).not.toBe(FakeWebSocket.CLOSED)

    wrapper.unmount()

    expect(FakeWebSocket.instances.every((socket) => socket.readyState === FakeWebSocket.CLOSED)).toBe(true)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('replays missed cursor events once before queued live events and deduplicates overlap', async () => {
    let resolveReplay!: (response: Response) => void
    const replayResponse = new Promise<Response>((resolve) => {
      resolveReplay = resolve
    })
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.startsWith('/api/realtime/events')) return replayResponse
      return Promise.resolve(jsonResponse({ proxies: [], system_config: {} }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const { WebSocketManager } = await import('../useWebSocket')
    const manager = WebSocketManager.getInstance()
    const received: number[] = []
    const subscriber = () => undefined
    const stopListening = manager.onMessage((event) => {
      if (typeof event.event_id === 'number') received.push(event.event_id)
    })

    manager.subscribe(subscriber)
    FakeWebSocket.instances[0].open()
    FakeWebSocket.instances[0].message({ type: 'test', event_id: 7, data: { test_id: 'seven' } })
    FakeWebSocket.instances[0].serverClose()

    await vi.advanceTimersByTimeAsync(1000)
    expect(FakeWebSocket.instances).toHaveLength(2)

    FakeWebSocket.instances[1].open()
    FakeWebSocket.instances[1].message({ type: 'test', event_id: 9, data: { test_id: 'nine' } })
    FakeWebSocket.instances[1].message({ type: 'test', event_id: 10, data: { test_id: 'ten' } })

    expect(received).toEqual([7])
    expect(fetchMock).toHaveBeenCalledWith('/api/realtime/events?since=7', {
      credentials: 'include'
    })

    resolveReplay(jsonResponse({
      since: 7,
      events: [
        { type: 'test', event_id: 8, data: { test_id: 'eight' } },
        { type: 'test', event_id: 9, data: { test_id: 'nine' } }
      ],
      gap: false,
      latest_event_id: 9,
      oldest_event_id: 1,
      retained_events: 9,
      max_retained_events: 500
    }))
    await flushPromises()

    expect(received).toEqual([7, 8, 9, 10])
    expect(manager.connectionStatus.value).toBe('connected')

    stopListening()
    manager.unsubscribe(subscriber)
  })

  it('never schedules reconnect after a terminal authentication close', async () => {
    const { WebSocketManager } = await import('../useWebSocket')
    const manager = WebSocketManager.getInstance()
    const subscriber = () => undefined

    manager.subscribe(subscriber)
    FakeWebSocket.instances[0].open()
    FakeWebSocket.instances[0].serverClose(4001, 'session expired')
    await flushPromises()

    expect(manager.connectionStatus.value).toBe('auth_failed')
    expect(vi.getTimerCount()).toBe(0)

    await vi.advanceTimersByTimeAsync(120_000)
    expect(FakeWebSocket.instances).toHaveLength(1)

    manager.unsubscribe(subscriber)
  })
})
