function normalizedExpectedUrl(baseUrl, route) {
  return new URL(route, baseUrl).toString()
}

export function validateLighthouseScenario(report, scenario, baseUrl, routeIdentity) {
  const expectedUrl = normalizedExpectedUrl(baseUrl, scenario.route)
  const finalUrl = new URL(report.finalDisplayedUrl)
  const expected = new URL(expectedUrl)

  if (finalUrl.origin !== expected.origin || finalUrl.pathname !== expected.pathname) {
    throw new Error(`unexpected final URL for ${scenario.id}: expected ${expectedUrl}, received ${report.finalDisplayedUrl}`)
  }

  if (!routeIdentity || routeIdentity.finalUrl !== expectedUrl || routeIdentity.selector !== scenario.readinessSelector || routeIdentity.selectorCount !== 1) {
    throw new Error(`route identity was not confirmed for ${scenario.id} at ${expectedUrl}`)
  }

  return routeIdentity
}
