import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { describe, expect, it } from 'vitest'
import {
  BUILD_PROVENANCE_FILENAME,
  recordBuildProvenance,
  verifyBuildProvenance,
} from '../build-artifact-provenance.mjs'

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), 'streamvault-build-provenance-'))
  await mkdir(join(root, 'src'), { recursive: true })
  await mkdir(join(root, 'public'), { recursive: true })
  await mkdir(join(root, 'dist', 'assets'), { recursive: true })
  await writeFile(join(root, 'src', 'main.ts'), 'export const mode = import.meta.env.VITE_USE_MOCK_DATA\n')
  await writeFile(join(root, 'public', 'icon.svg'), '<svg/>\n')
  await writeFile(join(root, 'index.html'), '<main></main>\n')
  await writeFile(join(root, 'vite.config.ts'), 'export default {}\n')
  await writeFile(join(root, 'package.json'), '{"type":"module"}\n')
  await writeFile(join(root, 'package-lock.json'), '{"lockfileVersion":3}\n')
  await writeFile(join(root, 'dist', 'index.html'), '<script src="/assets/app.js"></script>\n')
  await writeFile(join(root, 'dist', 'assets', 'app.js'), 'const mode=true\n')
  return root
}

describe('build artifact provenance', () => {
  it('binds reuse to the requested mode, source bytes, and complete dist bytes', async () => {
    const root = await fixture()
    await recordBuildProvenance(root, 'mock')

    await expect(verifyBuildProvenance(root, 'mock')).resolves.toMatchObject({ mode: 'mock', fileCount: 2 })
    await expect(verifyBuildProvenance(root, 'real')).rejects.toThrow(/mode mismatch/)

    await writeFile(join(root, 'dist', 'assets', 'app.js'), 'const mode=false\n')
    await expect(verifyBuildProvenance(root, 'mock')).rejects.toThrow(/artifact bytes changed/)

    await writeFile(join(root, 'dist', 'assets', 'app.js'), 'const mode=true\n')
    await recordBuildProvenance(root, 'mock')
    await writeFile(join(root, 'src', 'main.ts'), 'export const changed = true\n')
    await expect(verifyBuildProvenance(root, 'mock')).rejects.toThrow(/source bytes changed/)
  })

  it('fails closed when the provenance file is absent or malformed', async () => {
    const root = await fixture()
    await expect(verifyBuildProvenance(root, 'mock')).rejects.toThrow(/provenance is missing/)

    await writeFile(join(root, 'dist', BUILD_PROVENANCE_FILENAME), '{broken')
    await expect(verifyBuildProvenance(root, 'mock')).rejects.toThrow(/not valid JSON/)
    await rm(root, { recursive: true, force: true })
  })

  it('writes no timestamp or host-specific path into the deterministic marker', async () => {
    const root = await fixture()
    await recordBuildProvenance(root, 'real')
    const marker = await readFile(join(root, 'dist', BUILD_PROVENANCE_FILENAME), 'utf8')
    expect(marker).not.toContain(root)
    expect(marker).not.toMatch(/created|timestamp|20\d\d-/)
  })
})