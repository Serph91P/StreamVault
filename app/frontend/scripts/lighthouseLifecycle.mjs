export async function collectWithIsolatedBrowsers(cacheModes, launchBrowser, collect) {
  const reports = []
  for (const cacheMode of cacheModes) {
    const browser = await launchBrowser()
    try {
      reports.push(await collect(browser, cacheMode))
    } finally {
      await browser.kill()
    }
  }
  return reports
}
