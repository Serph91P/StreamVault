const FOCUSABLE_SELECTOR = 'a[href],button,input,select,textarea,[tabindex]'

export function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    .filter((el) => el.tabIndex >= 0 && !el.matches(':disabled,[disabled]') && el.offsetParent !== null)
}

/** Handle only Tab boundaries; callers own modality, stacking and restoration. */
export function containFocus(event: KeyboardEvent, container: HTMLElement) {
  if (event.key !== 'Tab') return
  const focusable = getFocusable(container)
  // Reverse the local candidates, not the DOM, so both directions share one boundary rule.
  if (event.shiftKey) focusable.reverse()
  const active = document.activeElement
  const target = focusable[0]
  if (!target || active === focusable.at(-1) || !container.contains(active)) {
    event.preventDefault()
    target?.focus()
  }
}
