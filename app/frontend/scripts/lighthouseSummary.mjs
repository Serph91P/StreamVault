function numericAudit(report, id) {
  const value = report.audits?.[id]?.numericValue
  return typeof value === 'number' ? value : null
}

function auditItemCount(report, id) {
  const items = report.audits?.[id]?.details?.items
  return Array.isArray(items) ? items.length : null
}

export function summarizeLighthouseReport(report) {
  const performanceScore = report.categories?.performance?.score
  return {
    performanceScore: typeof performanceScore === 'number' ? performanceScore : null,
    largestContentfulPaintMs: numericAudit(report, 'largest-contentful-paint'),
    cumulativeLayoutShift: numericAudit(report, 'cumulative-layout-shift'),
    totalBlockingTimeMs: numericAudit(report, 'total-blocking-time'),
    domNodes: numericAudit(report, 'dom-size') ?? numericAudit(report, 'dom-size-insight'),
    networkRequests: numericAudit(report, 'network-requests') ?? auditItemCount(report, 'network-requests'),
    totalByteWeight: numericAudit(report, 'total-byte-weight'),
  }
}
