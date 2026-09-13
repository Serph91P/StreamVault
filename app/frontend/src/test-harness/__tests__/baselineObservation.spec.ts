import { describe, expect, it } from 'vitest'
import { formatBaselineStageFailure } from '../../../tests/audit/baselineObservation'

describe('formatBaselineStageFailure', () => {
  it('preserves the failing collection stage and error message', () => {
    expect(formatBaselineStageFailure('readiness', new Error('wait timed out'))).toBe('readiness: wait timed out')
  })

  it('serializes non-Error failures without losing the stage', () => {
    expect(formatBaselineStageFailure('axe', 'injected script rejected')).toBe('axe: injected script rejected')
  })
})
