import { describe, expect, it } from 'vitest'
import { collectWithIsolatedBrowsers } from '../../../scripts/lighthouseLifecycle.mjs'

type Browser = {
  id: string
  kill: () => Promise<void>
}

describe('collectWithIsolatedBrowsers', () => {
  it('closes each browser before collecting the next measurement', async () => {
    const events: string[] = []
    const browsers: Browser[] = [
      { id: 'first', kill: async () => { events.push('kill:first') } },
      { id: 'second', kill: async () => { events.push('kill:second') } },
    ]
    let launchIndex = 0

    const result = await collectWithIsolatedBrowsers(
      ['cold', 'warm'],
      async () => {
        const browser = browsers[launchIndex]
        launchIndex += 1
        events.push(`launch:${browser.id}`)
        return browser
      },
      async (browser: Browser, cacheMode: string) => {
        events.push(`collect:${browser.id}:${cacheMode}`)
        return `${browser.id}:${cacheMode}`
      },
    )

    expect(result).toEqual(['first:cold', 'second:warm'])
    expect(events).toEqual([
      'launch:first',
      'collect:first:cold',
      'kill:first',
      'launch:second',
      'collect:second:warm',
      'kill:second',
    ])
  })
})
