import { describe, expect, it } from 'vitest'
import { expectGateFailure } from '../audit/gateEvidence'

describe('negative gate evidence helper', () => {
  it('accepts only the expected external gate failure', async () => {
    await expect(expectGateFailure(() => { throw new Error('touch target 20x20') }, /touch target/)).resolves.toBeUndefined()
  })

  it('fails when the negative fixture unexpectedly passes', async () => {
    await expect(expectGateFailure(() => undefined, /touch target/)).rejects.toThrow('unexpectedly passed')
  })

  it('fails when a fixture trips an unrelated gate', async () => {
    await expect(expectGateFailure(() => { throw new Error('server missing') }, /touch target/)).rejects.toThrow('wrong reason')
  })
})
