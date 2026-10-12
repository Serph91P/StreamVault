import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { readdir, readFile, rm } from 'node:fs/promises'
import { join, relative } from 'node:path'
import { checkPrecacheIntegrity } from './check-precache-integrity.mjs'
import { buildVerifiedArtifact } from './build-artifact-provenance.mjs'

const root = process.cwd()
const dist = join(root, 'dist')

async function manifest(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []

  for (const entry of entries) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      files.push(...await manifest(path))
    } else if (entry.isFile()) {
      files.push(`${relative(dist, path)} ${createHash('sha256').update(await readFile(path)).digest('hex')}`)
    }
  }

  return files.sort()
}

async function build(number) {
  await rm(dist, { recursive: true, force: true })
  await buildVerifiedArtifact(root, 'mock')

  const emittedSource = join(dist, 'src')
  if (existsSync(emittedSource)) {
    throw new Error(`Production build ${number} emitted source output at ${emittedSource}`)
  }

  await checkPrecacheIntegrity(join(dist, 'sw.js'))
  return manifest(dist)
}

const first = await build(1)
const second = await build(2)

if (first.join('\n') !== second.join('\n')) {
  throw new Error('Production build output differs between clean builds')
}

console.log(`Build output contract passed with ${first.length} files`)
