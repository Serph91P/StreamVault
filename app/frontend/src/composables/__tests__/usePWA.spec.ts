import { mount } from '@vue/test-utils'
import { defineComponent, h, type Ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const routerPush = vi.fn(() => Promise.resolve())

vi.mock('@/router', () => ({
  default: {
    push: routerPush,
  },
}))

interface PWAState {
  isInstallable: Ref<boolean>
  isInstalled: Ref<boolean>
  isOnline: Ref<boolean>
}

class MatchMediaStub extends EventTarget implements MediaQueryList {
  matches = false
  readonly media: string
  onchange: ((this: MediaQueryList, ev: MediaQueryListEvent) => unknown) | null = null
  readonly addEventListener = vi.fn(super.addEventListener.bind(this))
  readonly removeEventListener = vi.fn(super.removeEventListener.bind(this))

  constructor(media: string) {
    super()
    this.media = media
  }

  setMatches(matches: boolean) {
    this.matches = matches
    this.dispatchEvent(new Event('change'))
  }

  addListener(listener: ((this: MediaQueryList, ev: MediaQueryListEvent) => unknown) | null) {
    if (listener) this.addEventListener('change', listener as EventListener)
  }

  removeListener(listener: ((this: MediaQueryList, ev: MediaQueryListEvent) => unknown) | null) {
    if (listener) this.removeEventListener('change', listener as EventListener)
  }

  dispatchEvent(event: Event): boolean {
    return super.dispatchEvent(event)
  }
}

class ServiceWorkerContainerStub extends EventTarget {
  readonly ready = new Promise<ServiceWorkerRegistration>(() => undefined)
  readonly addEventListener = vi.fn(super.addEventListener.bind(this))
  readonly removeEventListener = vi.fn(super.removeEventListener.bind(this))
  readonly getRegistration = vi.fn(async () => undefined)
}

function mountPWA() {
  let state: PWAState | undefined
  const Harness = defineComponent({
    setup() {
      state = usePWA()
      return () => h('div')
    },
  })
  const wrapper = mount(Harness)
  return { wrapper, state: state! }
}

const originalServiceWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')
let standaloneMedia: MatchMediaStub
let serviceWorker: ServiceWorkerContainerStub
let windowAdds: ReturnType<typeof vi.spyOn>
let windowRemoves: ReturnType<typeof vi.spyOn>

beforeEach(async () => {
  routerPush.mockClear()
  standaloneMedia = new MatchMediaStub('(display-mode: standalone)')
  serviceWorker = new ServiceWorkerContainerStub()

  vi.stubGlobal('matchMedia', vi.fn((query: string) =>
    query === standaloneMedia.media ? standaloneMedia : new MatchMediaStub(query),
  ))
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: serviceWorker,
  })
  windowAdds = vi.spyOn(window, 'addEventListener')
  windowRemoves = vi.spyOn(window, 'removeEventListener')

  const { usePWA: importedUsePWA } = await import('../usePWA')
  usePWA = importedUsePWA
})

afterEach(() => {
  vi.unstubAllGlobals()
  if (originalServiceWorker) {
    Object.defineProperty(navigator, 'serviceWorker', originalServiceWorker)
  } else {
    Reflect.deleteProperty(navigator, 'serviceWorker')
  }
})

let usePWA: typeof import('../usePWA').usePWA

function listenersFor(calls: readonly (readonly unknown[])[], eventName: string) {
  return calls
    .filter((call) => call[0] === eventName)
    .map((call) => call[1])
}

describe('usePWA listener lifecycle', () => {
  it('balances every owned listener with the same callback across repeated mount cycles', () => {
    for (let cycle = 0; cycle < 2; cycle += 1) {
      const { wrapper } = mountPWA()
      wrapper.unmount()
    }

    for (const eventName of ['online', 'offline', 'beforeinstallprompt', 'appinstalled']) {
      const added = listenersFor(windowAdds.mock.calls, eventName)
      const removed = listenersFor(windowRemoves.mock.calls, eventName)
      expect(added).toHaveLength(2)
      expect(removed).toEqual(added)
    }

    const mediaAdds = standaloneMedia.addEventListener.mock.calls
      .filter(([type]) => type === 'change')
      .map(([, listener]) => listener)
    const mediaRemoves = standaloneMedia.removeEventListener.mock.calls
      .filter(([type]) => type === 'change')
      .map(([, listener]) => listener)
    expect(mediaAdds).toHaveLength(2)
    expect(mediaRemoves).toEqual(mediaAdds)

    const workerAdds = serviceWorker.addEventListener.mock.calls
      .filter(([type]) => type === 'message')
      .map(([, listener]) => listener)
    const workerRemoves = serviceWorker.removeEventListener.mock.calls
      .filter(([type]) => type === 'message')
      .map(([, listener]) => listener)
    expect(workerAdds).toHaveLength(2)
    expect(workerRemoves).toEqual(workerAdds)
  })

  it('preserves install, display-mode, connectivity, and service-worker navigation behavior while mounted', () => {
    const { wrapper, state } = mountPWA()

    window.dispatchEvent(new Event('offline'))
    expect(state.isOnline.value).toBe(false)

    const installEvent = new Event('beforeinstallprompt', { cancelable: true })
    window.dispatchEvent(installEvent)
    expect(installEvent.defaultPrevented).toBe(true)
    expect(state.isInstallable.value).toBe(true)

    standaloneMedia.setMatches(true)
    expect(state.isInstalled.value).toBe(true)

    window.dispatchEvent(new Event('appinstalled'))
    expect(state.isInstalled.value).toBe(true)
    expect(state.isInstallable.value).toBe(false)

    serviceWorker.dispatchEvent(new MessageEvent('message', {
      data: { type: 'navigate', url: '/settings?tab=pwa#install' },
    }))
    expect(routerPush).toHaveBeenCalledWith('/settings?tab=pwa#install')

    wrapper.unmount()
  })

  it('leaves no callback that can mutate state or route after unmount', () => {
    const { wrapper, state } = mountPWA()
    wrapper.unmount()

    window.dispatchEvent(new Event('offline'))
    window.dispatchEvent(new Event('appinstalled'))
    const installEvent = new Event('beforeinstallprompt', { cancelable: true })
    window.dispatchEvent(installEvent)
    standaloneMedia.setMatches(true)
    serviceWorker.dispatchEvent(new MessageEvent('message', {
      data: { type: 'navigate', url: '/settings' },
    }))

    expect(state.isOnline.value).toBe(navigator.onLine)
    expect(state.isInstalled.value).toBe(false)
    expect(state.isInstallable.value).toBe(false)
    expect(installEvent.defaultPrevented).toBe(false)
    expect(routerPush).not.toHaveBeenCalled()
  })
})
