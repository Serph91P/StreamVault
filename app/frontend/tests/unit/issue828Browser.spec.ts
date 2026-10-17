import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Locator } from '@playwright/test'
import { clickAndMeasureOrigin, observeOriginClick, requireOriginScroll } from '../fixtures/issue828Browser'

// This suite exercises only click observation; binary media loading belongs to
// the separate genuine HTTP/media fixture contract and browser suites.
vi.mock('../fixtures/media/issue828Media', () => ({ localSeekMedia: vi.fn() }))

afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks() })

describe('origin click measurement contract (unit doubles, NOT trusted browser evidence)', () => {
  it('rejects a missing target and absent clicks', () => {
    expect(() => observeOriginClick(null)).toThrow('missing')
    const target = document.createElement('button')
    const sample = observeOriginClick(target)
    try { expect(() => requireOriginScroll(sample)).toThrow('exactly one trusted') }
    finally { sample.cleanup() }
  })

  it('captures synchronously in capture phase, once, without stopping navigation', () => {
    const target = document.createElement('button')
    document.body.append(target)
    const add = vi.spyOn(target, 'addEventListener')
    const sample = observeOriginClick(target)
    expect(add).toHaveBeenCalledWith('click', expect.any(Function), { once: true, capture: true })
    const bubble = vi.fn(() => { expect(sample.clicks).toBe(1) })
    target.addEventListener('click', bubble)
    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(123.5)
    const event = new MouseEvent('click', { bubbles: true, cancelable: true })
    target.dispatchEvent(event)
    expect(sample).toMatchObject({ clicks: 1, trusted: false, scroll: 123.5 })
    expect(event.defaultPrevented).toBe(false)
    expect(bubble).toHaveBeenCalledOnce()
    expect(() => requireOriginScroll(sample)).toThrow('trusted')
    target.dispatchEvent(new MouseEvent('click'))
    expect(sample.clicks).toBe(1)
    sample.cleanup()
  })

  it('removes an unfired capture listener on cleanup', () => {
    const target = document.createElement('button')
    const remove = vi.spyOn(target, 'removeEventListener')
    const sample = observeOriginClick(target)
    sample.cleanup()
    expect(remove).toHaveBeenCalledWith('click', expect.any(Function), true)
    target.click()
    expect(sample.clicks).toBe(0)
  })

  it.each([null, 0, -1, NaN, Infinity, -Infinity])('rejects invalid positive scroll %s', scroll => {
    expect(() => requireOriginScroll({ clicks: 1, trusted: true, scroll })).toThrow('positive scroll')
  })
  it.each([0, 2])('rejects %s clicks even with a positive trusted sample', clicks => {
    expect(() => requireOriginScroll({ clicks, trusted: true, scroll: 123 })).toThrow('exactly one')
  })
  it('preserves a valid fractional sample without rounding', () => {
    expect(requireOriginScroll({ clicks: 1, trusted: true, scroll: 123.5 })).toBe(123.5)
  })

  function locatorDouble(failure?: 'click' | 'cleanup' | 'untrusted') {
    const cleanup = vi.fn(() => { if (failure === 'cleanup') throw new Error('cleanup failure') })
    const dispose = vi.fn()
    const sample = { clicks: 1, trusted: failure !== 'untrusted', scroll: 789.25, cleanup }
    const handle = { evaluate: vi.fn(async (read: (value: typeof sample) => unknown) => read(sample)), dispose }
    const target = {
      evaluateHandle: vi.fn(async () => handle),
      click: vi.fn(async () => { if (failure === 'click') throw new Error('click failure') }),
    }
    return { target: target as unknown as Locator, handle, cleanup, dispose, click: target.click }
  }
  it('uses exactly one ordinary click then cleans and disposes its owned handle', async () => {
    const fixture = locatorDouble()
    expect(await clickAndMeasureOrigin(fixture.target)).toBe(789.25)
    expect(fixture.click).toHaveBeenCalledExactlyOnceWith()
    expect(fixture.cleanup).toHaveBeenCalledOnce()
    expect(fixture.dispose).toHaveBeenCalledOnce()
  })
  it.each(['click', 'cleanup', 'untrusted'] as const)('cleans/disposes after %s failure', async failure => {
    const fixture = locatorDouble(failure)
    await expect(clickAndMeasureOrigin(fixture.target)).rejects.toThrow()
    expect(fixture.click).toHaveBeenCalledOnce()
    expect(fixture.cleanup).toHaveBeenCalledOnce()
    expect(fixture.dispose).toHaveBeenCalledOnce()
  })
})
