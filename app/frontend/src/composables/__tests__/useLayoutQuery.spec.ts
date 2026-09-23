import { effectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useLayoutQuery } from '../useLayoutQuery'

interface MatchMediaStub {
  query: string
  setMatches: (matches: boolean) => void
}

function stubMatchMedia(initialMatches = false): MatchMediaStub {
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  let matches = initialMatches
  let query = ''

  vi.stubGlobal('matchMedia', vi.fn((requestedQuery: string) => {
    query = requestedQuery
    return {
      get matches() { return matches },
      media: requestedQuery,
      addEventListener: (_: 'change', listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
      removeEventListener: (_: 'change', listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
      dispatchEvent: () => true,
    }
  }))

  return {
    get query() { return query },
    setMatches(nextMatches) {
      matches = nextMatches
      for (const listener of listeners) listener({ matches, media: query } as MediaQueryListEvent)
    },
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('useLayoutQuery', () => {
  it('uses the preserved player boundary and reacts to viewport changes', () => {
    const matchMedia = stubMatchMedia(false)
    const scope = effectScope()
    const query = scope.run(() => useLayoutQuery('player'))

    expect(matchMedia.query).toBe('(max-width: 767px)')
    expect(query?.value).toBe(false)

    matchMedia.setMatches(true)
    expect(query?.value).toBe(true)
    scope.stop()
  })

  it('uses the preserved shell boundary and removes its listener when disposed', () => {
    const matchMedia = stubMatchMedia(true)
    const scope = effectScope()
    const query = scope.run(() => useLayoutQuery('shell'))

    expect(matchMedia.query).toBe('(max-width: 1023.98px)')
    expect(query?.value).toBe(true)

    scope.stop()
    matchMedia.setMatches(false)
    expect(query?.value).toBe(true)
  })
})
