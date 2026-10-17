/** Serializable, test-only predicate: an empty pre-paint animation list is not readiness. */
export function isMotionSettled(element: Element): boolean {
  if (!element.isConnected) return false
  const view = element.ownerDocument.defaultView
  if (!view) return false
  for (let current: Element | null = element; current; current = current.parentElement) {
    const style = view.getComputedStyle(current)
    if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' ||
        (style.opacity !== '' && Number(style.opacity) !== 1) ||
        Array.from(current.classList).some(name => /-(enter|leave)-(from|active|to)$/.test(name))) return false
    const animations = current.getAnimations({ subtree: current === element })
    if (animations.some(animation =>
      (animation.pending || animation.playState === 'running' || animation.playState === 'paused') &&
      Number.isFinite(animation.effect?.getComputedTiming().endTime)
    )) return false
  }
  return true
}
