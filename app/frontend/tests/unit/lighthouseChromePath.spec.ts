import { describe, expect, it } from 'vitest'
import { validateLighthouseChromePath } from '../../scripts/lighthouseChromePath.mjs'

describe('validateLighthouseChromePath', () => {
  it('explains how to supply a browser when the resolved executable is unavailable', async () => {
    await expect(validateLighthouseChromePath('/missing/chrome', async () => {
      throw new Error('ENOENT')
    })).rejects.toThrow('Lighthouse Chrome executable is unavailable at /missing/chrome. Set LIGHTHOUSE_CHROME_PATH to an installed Chromium or Chrome executable.')
  })

  it('returns an executable path after the caller confirms it can be run', async () => {
    await expect(validateLighthouseChromePath('/available/chrome', async () => undefined)).resolves.toBe('/available/chrome')
  })
})
