import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatRecordingDuration } from '../recordingDuration'

// Independent legacy bodies, retained as compatibility oracles for both callers.
function cardLegacy(start: string | null, end: string | null) {
  if (!start) return '-'
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : new Date()
  const diffMs = endDate.getTime() - startDate.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMins / 60)
  const mins = diffMins % 60
  if (hours > 0) { return `${hours}h ${mins}m` }
  return `${mins}m`
}
function viewLegacy(start?: string, end?: string): string {
  if (!start) return '-'
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : new Date()
  const diffMs = endDate.getTime() - startDate.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMins / 60)
  const mins = diffMins % 60
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}
const start = '2026-09-03T10:00:00Z'
const cases: [string | null | undefined, string | null | undefined][] = [
  [undefined, undefined], [null, null], ['', 'invalid'], ['invalid', null], [start, 'invalid'],
  [start, undefined], [start, null], [start, ''], [start, start],
  ...[-3600001, -3600000, -60001, -60000, -1, 1, 59999, 60000, 3599999, 3600000, 3660000]
    .map(ms => [start, new Date(Date.parse(start) + ms).toISOString()] as [string, string]),
  ['2026-03-29T01:30:00+01:00', '2026-03-29T03:30:00+02:00'],
  ['1900-01-01T00:00:00Z', '2100-01-01T00:00:00Z'],
]
afterEach(() => vi.useRealTimers())
describe('recording duration legacy compatibility', () => {
  it.each(cases)('preserves both exact legacy outputs for %s to %s', (from, to) => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-03T13:05:00Z'))
    const result = formatRecordingDuration(from, to)
    expect(result).toBe(cardLegacy(from ?? null, to ?? null))
    expect(result).toBe(viewLegacy(from ?? undefined, to ?? undefined))
  })
})
