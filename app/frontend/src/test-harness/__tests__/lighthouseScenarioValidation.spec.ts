import { describe, expect, it } from 'vitest'
import { validateLighthouseScenario } from '../../../scripts/lighthouseScenarioValidation.mjs'

describe('validateLighthouseScenario', () => {
  const scenario = {
    id: 'mobile-streamers',
    route: '/streamers',
    readinessSelector: '.streamers-view',
  }

  it('rejects a report redirected to login before it can be accepted as route evidence', () => {
    expect(() => validateLighthouseScenario({
      finalDisplayedUrl: 'http://127.0.0.1:4180/auth/login',
    }, scenario, 'http://127.0.0.1:4180')).toThrow(/unexpected final URL/)
  })

  it('rejects a report without one matching rendered route root', () => {
    for (const routeIdentity of [
      undefined,
      { finalUrl: 'http://127.0.0.1:4180/', selector: '.streamers-view', selectorCount: 1 },
      { finalUrl: 'http://127.0.0.1:4180/streamers', selector: '.home-view', selectorCount: 1 },
      { finalUrl: 'http://127.0.0.1:4180/streamers', selector: '.streamers-view', selectorCount: 0 },
      { finalUrl: 'http://127.0.0.1:4180/streamers', selector: '.streamers-view', selectorCount: 2 },
    ]) {
      expect(() => validateLighthouseScenario({
        finalDisplayedUrl: 'http://127.0.0.1:4180/streamers',
      }, scenario, 'http://127.0.0.1:4180', routeIdentity)).toThrow(/route identity was not confirmed/)
    }
  })

  it('accepts the intended route only after matching rendered route identity is observed', () => {
    expect(validateLighthouseScenario({
      finalDisplayedUrl: 'http://127.0.0.1:4180/streamers',
    }, scenario, 'http://127.0.0.1:4180', {
      finalUrl: 'http://127.0.0.1:4180/streamers',
      selector: '.streamers-view',
      selectorCount: 1,
    })).toEqual({
      finalUrl: 'http://127.0.0.1:4180/streamers',
      selector: '.streamers-view',
      selectorCount: 1,
    })
  })
})
