import { onScopeDispose, readonly, ref } from 'vue'
import { layoutQueries, type LayoutQueryName } from './layoutQueries.generated'

export type { LayoutQueryName }

/**
 * Tracks one named responsive query from the generated owner.
 *
 * The value is initialized synchronously so shell consumers do not flash an
 * incompatible layout on the first client render.
 */
export function useLayoutQuery(name: LayoutQueryName) {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return readonly(ref(false))

  const mediaQuery = window.matchMedia(layoutQueries[name])
  const matches = ref(mediaQuery.matches)
  const update = (event: MediaQueryListEvent) => { matches.value = event.matches }
  mediaQuery.addEventListener('change', update)
  onScopeDispose(() => mediaQuery.removeEventListener('change', update))

  return readonly(matches)
}
