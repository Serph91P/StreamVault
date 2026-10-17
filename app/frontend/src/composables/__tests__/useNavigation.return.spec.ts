import { reactive } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { prepareVideoReturn, takeVideoReturnExpansion } from '../useNavigation'

const origin = '/streamers/42?tab=videos&sort=oldest&source=history'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  history.replaceState({}, '', '/')
})

describe('video return entry expansion metadata', () => {
  it('snapshots cloneable row state without changing the URL or Router fields and consumes only its own data', () => {
    const routerState = { back: '/streamers', current: origin, forward: null, position: 3, replaced: true }
    history.replaceState({ ...routerState, foreign: 'retained' }, '', origin)
    vi.stubGlobal('scrollY', 738)
    const replace = vi.spyOn(history, 'replaceState')
    const expanded = reactive({ 1: true, 3: false, 4: true })
    prepareVideoReturn(origin, expanded)
    expect(() => structuredClone(replace.mock.calls[0]![0])).not.toThrow()
    expect(location.pathname + location.search).toBe(origin)
    expect(history.state).toMatchObject({ ...routerState, foreign: 'retained', svrs: 738 })
    expanded[1] = false
    expect(takeVideoReturnExpansion(origin)).toEqual({ 1: true, 3: false, 4: true })
    expect(history.state).toEqual({ ...routerState, foreign: 'retained', svrs: 738 })
    expect(takeVideoReturnExpansion(origin)).toEqual({})
  })

  it.each([
    null, 4, 'invalid', [],
    { origin, expanded: null }, { origin, expanded: [] },
    { origin, expanded: { 1: 'true' } },
    { origin, expanded: { '-1': true } },
    { origin, expanded: { Infinity: true } },
    { origin, expanded: { '1.5': true } },
    { origin, expanded: { '__proto__': null, other: true } },
    { origin: '/streamers/77?tab=videos', expanded: { 1: true } },
    { origin: '/streamers/42?tab=events', expanded: { 1: true } },
    { origin: origin + '&sort=newest', expanded: { 1: true } },
  ])('discards malformed or unrelated entry metadata %j', svre => {
    history.replaceState({ svre, position: 8 }, '', origin)
    expect(takeVideoReturnExpansion(origin)).toEqual({})
    expect(history.state).toEqual({ position: 8 })
  })

  it('does not accept an external origin or leak rows into other existing return callers', () => {
    history.replaceState({ position: 8 }, '', origin)
    prepareVideoReturn('//example.invalid', { 1: true })
    expect(history.state).toEqual({ position: 8 })
    prepareVideoReturn(origin, { 1: true })
    prepareVideoReturn('/videos?q=alpha')
    expect(takeVideoReturnExpansion(origin)).toEqual({})
  })
})
