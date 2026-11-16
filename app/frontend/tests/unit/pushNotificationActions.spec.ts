import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { describe, expect, it } from 'vitest'

const source = readFileSync('public/push-sw.js', 'utf8')

describe('public push notification actions', () => {
  for (const hasClient of [false, true]) {
    it.each(['', 'open', 'dismiss'])(`handles %s with existing client=${hasClient}`, async action => {
      const effects: unknown[] = []
      const listeners: Record<string, (event: unknown) => void> = {}
      let completion: Promise<void> | undefined
      runInNewContext(source, {
        URL,
        console,
        self: {
          location: { origin: 'https://streamvault.example' },
          addEventListener: (name: string, callback: (event: unknown) => void) => { listeners[name] = callback }
        },
        clients: {
          matchAll: async () => hasClient ? [{
            url: 'https://streamvault.example/',
            focus: async () => { effects.push('focus') },
            postMessage: (message: unknown) => { effects.push(message) }
          }] : [],
          openWindow: async (url: string) => { effects.push(url) }
        }
      })
      listeners.notificationclick({
        action,
        notification: {
          data: { target_url: '/streamer/owned-channel' },
          close: () => { effects.push('close') }
        },
        waitUntil: (promise: Promise<void>) => { completion = promise }
      })
      expect(completion).toBeDefined()
      await completion
      const target = 'https://streamvault.example/streamers/owned-channel'
      expect(effects).toEqual(action === 'dismiss' ? ['close'] : hasClient
        ? ['focus', { type: 'navigate', url: target }, 'close']
        : [target, 'close'])
    })
  }
})
