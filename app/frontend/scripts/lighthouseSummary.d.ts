export interface LighthouseBaselineSummary {
  performanceScore: number | null
  largestContentfulPaintMs: number | null
  cumulativeLayoutShift: number | null
  totalBlockingTimeMs: number | null
  domNodes: number | null
  networkRequests: number | null
  totalByteWeight: number | null
}

export function summarizeLighthouseReport(report: {
  categories?: { performance?: { score?: number } }
  audits?: Record<string, { numericValue?: number }>
}): LighthouseBaselineSummary
