import { afterEach, describe, expect, it, vi } from 'vitest'
import { containFocus, getFocusable } from '../focus'

afterEach(() => { document.body.innerHTML = ''; vi.restoreAllMocks() })

describe('shared focus boundaries', () => {
  it('excludes disabled and unlaid-out controls and preserves interior/native non-Tab keys', () => {
    document.body.innerHTML = '<div><button>first</button><button disabled>disabled</button><button hidden>hidden</button><button>last</button></div>'
    const container = document.body.firstElementChild as HTMLElement
    const buttons = Array.from(container.querySelectorAll('button'))
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockImplementation(function (this: HTMLElement) { return this.hidden ? null : document.body })
    expect(getFocusable(container)).toEqual([buttons[0], buttons[3]])
    buttons[0].focus()
    const forward = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true })
    containFocus(forward, container)
    expect(forward.defaultPrevented).toBe(false)
    const escape = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
    containFocus(escape, container)
    expect(escape.defaultPrevented).toBe(false)
    const reverse = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true })
    containFocus(reverse, container)
    expect(reverse.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(buttons[3])
    const wrap = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true })
    containFocus(wrap, container)
    expect(wrap.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(buttons[0])
  })

  it('excludes negative tabindex on native and generic controls', () => {
    document.body.innerHTML = '<div><button id="first">first</button><button tabindex="-1">negative button</button><a href="#" tabindex="-2">negative link</a><input tabindex="-1"><select tabindex="-1"></select><textarea tabindex="-1"></textarea><div tabindex="-3"></div><button id="last">last</button></div>'
    const container = document.body.firstElementChild as HTMLElement
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    expect(getFocusable(container).map(el => el.id)).toEqual(['first', 'last'])
  })

  it('uses inherited fieldset disability, preserving only its first-legend exception', () => {
    document.body.innerHTML = '<div><button id="first">first</button><fieldset disabled><legend><button id="legend">first legend exception</button></legend><button>inherited disabled</button><legend><button>second legend disabled</button></legend><input><select></select><textarea></textarea></fieldset><a href="#" disabled>explicit disabled</a><button id="last">last</button></div>'
    const container = document.body.firstElementChild as HTMLElement
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    expect(getFocusable(container).map(el => el.id)).toEqual(['first', 'legend', 'last'])
    const first = document.getElementById('first')!
    const last = document.getElementById('last')!
    first.focus()
    containFocus(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true }), container)
    expect(document.activeElement).toBe(last)
  })

  it('keeps hidden inputs and controls with no layout out of the tab cycle', () => {
    document.body.innerHTML = '<div><button id="visible">visible</button><input type="hidden"><button hidden>hidden</button><div style="display:none"><button>hidden ancestor</button></div><input id="input"><a href="#" id="link">link</a><div tabindex="0" id="custom"></div></div>'
    const container = document.body.firstElementChild as HTMLElement
    // jsdom has no layout: model only the native offsetParent boundary, not
    // tabIndex or :disabled, which are exercised by the real DOM implementation.
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockImplementation(function (this: HTMLElement) {
      return this.closest('[hidden], [style="display:none"]') || this.matches('input[type="hidden"]') ? null : document.body
    })
    expect(getFocusable(container).map(el => el.id)).toEqual(['visible', 'input', 'link', 'custom'])
  })

  it('prevents focus escape from an empty container without inventing a target', () => {
    const container = document.createElement('div')
    const event = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true })
    containFocus(event, container)
    expect(event.defaultPrevented).toBe(true)
  })
})
