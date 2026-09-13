function numericAudit(report, id) {
  const value = report.audits?.[id]?.numericValue
  return typeof value === 'number' ? value : null
}

export function summarizeLighthouseReport(report) {
  const performanceScore = report.categories?.performance?.score
  return {
    performanceScore: typeof performanceScore === 'number' ? performanceScore : null,
    largestContentfulPaintMs: numericAudit(report, 'largest-contentful-paint'),
    cumulativeLayoutShift: numericAudit(report, 'cumulative-layout-shift'),
    totalBlockingTimeMs: numericAudit(report, 'total-blocking-time'),
    domNodes: numericAudit(report, 'dom-size'),
    networkRequests: numericAudit(report, 'network-requests'),
    totalByteWeight: numericAudit(report, 'total-byte-weight'),
  }
}
