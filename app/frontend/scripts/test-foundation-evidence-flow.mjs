import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdtemp, readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
const source = resolve(frontendRoot, 'foundation-test-results')
const delivery = await mkdtemp(join(tmpdir(), 'streamvault-foundation-delivery-'))

function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, encoding: 'utf8', stdio: 'inherit' })
  if (result.status !== 0) process.exit(result.status ?? 1)
}

run('npm', ['run', 'test:foundation-browser'])
run('npm', ['run', 'test:e2e', '--', 'tests/e2e/pwa-manifest.spec.ts', '--project', 'desktop'])
run(process.execPath, ['scripts/package-foundation-evidence.mjs', '--source', source, '--output', delivery])

async function verifyManifest() {
  const manifest = await readFile(join(delivery, 'FOUNDATION-SHA256SUMS'), 'utf8')
  const entries = manifest.trim().split('\n')
  if (entries.length !== 4) throw new Error(`expected four packaged foundation captures, found ${entries.length}`)
  for (const entry of entries) {
    const match = entry.match(/^([a-f0-9]{64})  (foundation-(?:mobile|desktop)-(?:dark|light)\.png)$/)
    if (!match) throw new Error(`invalid foundation manifest entry: ${entry}`)
    const actual = createHash('sha256').update(await readFile(join(delivery, match[2]))).digest('hex')
    if (actual !== match[1]) throw new Error(`foundation manifest mismatch: ${match[2]}`)
  }
}

await verifyManifest()
run('npm', ['run', 'test:foundation-browser'])
await verifyManifest()
console.log(`Verified foundation capture -> regular E2E -> package flow in ${delivery}`)