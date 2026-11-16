import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RegisterSWOptions } from 'vite-plugin-pwa/types'

const boundary = vi.hoisted(() => ({ options: {} as RegisterSWOptions, update: vi.fn(async () => {}) }))
const register = (options: RegisterSWOptions) => {
  boundary.options = options
  return boundary.update
}

beforeEach(() => {
  vi.resetModules()
  boundary.update.mockReset().mockResolvedValue(undefined)
  vi.stubGlobal('location', { href: 'http://localhost/auth/login#install', assign: vi.fn(), reload: vi.fn() })
})

describe('page-owned PWA update lifecycle', () => {
  it('keeps waiting state without navigating and exposes it to later consumers', async () => {
    const state = await import('../pwa-update')
    state.initializePWAUpdates(register)
    boundary.options.onNeedRefresh?.()
    expect(state.pwaUpdateAvailable.value).toBe(true)
    expect(location.assign).not.toHaveBeenCalled()
    const laterConsumer = await import('../pwa-update')
    expect(laterConsumer.pwaUpdateAvailable.value).toBe(true)
  })

  it('intercepts foreign activation without releasing login or playback drafts', async () => {
    const state = await import('../pwa-update')
    state.initializePWAUpdates(register)
    boundary.options.onNeedReload?.()
    boundary.options.onNeedReload?.()
    expect(state.pwaUpdateAvailable.value).toBe(true)
    expect(location.assign).not.toHaveBeenCalled()
  })

  it('does not turn a successful login without an update into a document transition', async () => {
    const state = await import('../pwa-update')
    state.initializePWAUpdates(register)
    expect(await state.applyPWAUpdate('/settings?tab=pwa#install')).toBe(false)
    expect(location.assign).not.toHaveBeenCalled()
  })

  it('activates a waiting update once and navigates directly to the login return target once', async () => {
    const state = await import('../pwa-update')
    state.initializePWAUpdates(register)
    boundary.options.onNeedRefresh?.()
    expect(await state.applyPWAUpdate('/settings?tab=pwa#install')).toBe(true)
    expect(await state.applyPWAUpdate('/other')).toBe(true)
    expect(boundary.update).toHaveBeenCalledTimes(1)
    expect(location.assign).not.toHaveBeenCalled()
    boundary.options.onNeedReload?.()
    boundary.options.onNeedReload?.()
    expect(location.assign).toHaveBeenCalledExactlyOnceWith('/settings?tab=pwa#install')
  })

  it('applies an already active foreign update through a real document transition, not inert skipWaiting', async () => {
    const state = await import('../pwa-update')
    state.initializePWAUpdates(register)
    boundary.options.onNeedReload?.()
    expect(await state.applyPWAUpdate()).toBe(true)
    expect(location.reload).toHaveBeenCalledOnce()
    expect(location.assign).not.toHaveBeenCalled()
    expect(boundary.update).not.toHaveBeenCalled()
  })

  it('consumes native waiting state when login wins the Workbox prompt notification race', async () => {
    const waiting = {} as ServiceWorker
    const registration = { waiting } as ServiceWorkerRegistration
    const container = new EventTarget()
    vi.stubGlobal('navigator', { serviceWorker: container })
    const state = await import('../pwa-update')
    state.initializePWAUpdates(register)
    boundary.options.onRegisteredSW?.('/sw.js', registration)
    // The worker is already waiting, but Workbox's delayed onNeedRefresh has not fired.
    expect(await state.applyPWAUpdate('/settings?section=pwa#install')).toBe(true)
    expect(boundary.update).toHaveBeenCalledOnce()
    container.dispatchEvent(new Event('controllerchange'))
    boundary.options.onNeedReload?.()
    expect(location.assign).toHaveBeenCalledExactlyOnceWith('/settings?section=pwa#install')
  })

  it.each(['https://outside.test', '//outside.test', '/\\\\outside.test', 'javascript:alert(1)'])(
    'never turns a successful login into an external document navigation: %s', async target => {
      const state = await import('../pwa-update')
      state.initializePWAUpdates(register)
      boundary.options.onNeedReload?.()
      expect(await state.applyPWAUpdate(target)).toBe(true)
      expect(location.assign).toHaveBeenCalledExactlyOnceWith('/')
    },
  )

  it('retains pending state and allows deliberate retry when activation fails', async () => {
    const state = await import('../pwa-update')
    state.initializePWAUpdates(register)
    boundary.options.onNeedRefresh?.()
    boundary.update.mockRejectedValueOnce(new Error('registration unavailable'))
    await expect(state.applyPWAUpdate('/settings')).rejects.toThrow('registration unavailable')
    expect(state.pwaUpdateAvailable.value).toBe(true)
    expect(location.assign).not.toHaveBeenCalled()
    expect(await state.applyPWAUpdate('/settings')).toBe(true)
    boundary.options.onNeedReload?.()
    expect(location.assign).toHaveBeenCalledExactlyOnceWith('/settings')
  })
})
