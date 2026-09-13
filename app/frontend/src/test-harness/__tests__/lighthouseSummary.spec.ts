import { describe, expect, it } from 'vitest'
import { summarizeLighthouseReport } from '../../../scripts/lighthouseSummary.mjs'

describe('summarizeLighthouseReport', () => {
  it('extracts representative runtime metrics without inventing absent audits', () => {
    const summary = summarizeLighthouseReport({
      categories: { performance: { score: 0.91 } },
      audits: {
        'largest-contentful-paint': { numericValue: 1234 },
        'cumulative-layout-shift': { numericValue: 0.02 },
        'total-blocking-time': { numericValue: 18 },
        'dom-size': { numericValue: 42 },
        'network-requests': { numericValue: 7 },
        'total-byte-weight': { numericValue: 2048 },
        'unused-javascript': {},
      },
    })

    expect(summary).toEqual({
      performanceScore: 0.91,
      largestContentfulPaintMs: 1234,
      cumulativeLayoutShift: 0.02,
      totalBlockingTimeMs: 18,
      domNodes: 42,
      networkRequests: 7,
      totalByteWeight: 2048,
    })
  })

  it('supports Lighthouse 13 DOM and network audit shapes', () => {
    const summary = summarizeLighthouseReport({
      categories: { performance: { score: 1 } },
      audits: {
        'dom-size-insight': { numericValue: 347 },
        'network-requests': { details: { items: [{}, {}, {}] } },
      },
    })

    expect(summary.domNodes).toBe(347)
    expect(summary.networkRequests).toBe(3)
  })
})
