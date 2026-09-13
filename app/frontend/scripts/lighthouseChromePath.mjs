import { constants } from 'node:fs'
import { access } from 'node:fs/promises'

export async function validateLighthouseChromePath(chromePath, accessExecutable = access) {
  try {
    await accessExecutable(chromePath, constants.X_OK)
  } catch {
    throw new Error(`Lighthouse Chrome executable is unavailable at ${chromePath}. Set LIGHTHOUSE_CHROME_PATH to an installed Chromium or Chrome executable.`)
  }
  return chromePath
}
