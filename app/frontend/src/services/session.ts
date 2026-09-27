export interface LoginLocation {
  path: '/auth/login'
  query?: { returnTo: string }
}

const AUTH_PATHS = new Set(['/auth/login', '/auth/setup'])

/**
 * Keeps post-auth navigation inside this SPA. Return locations are intentionally
 * paths, never absolute URLs, so an expired session cannot become an open redirect.
 */
export function getSafeReturnPath(candidate: unknown): string {
  if (typeof candidate !== 'string' || !candidate.startsWith('/') || candidate.startsWith('//')) {
    return '/'
  }

  const path = candidate.split(/[?#]/, 1)[0]
  return AUTH_PATHS.has(path) ? '/' : candidate
}

export function loginLocationFor(candidate: unknown): LoginLocation {
  const returnTo = getSafeReturnPath(candidate)
  return returnTo === '/'
    ? { path: '/auth/login' }
    : { path: '/auth/login', query: { returnTo } }
}
