import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { readdir, readFile, rm } from 'node:fs/promises'
import { join, relative } from 'node:path'
import { spawnSync } from 'node:child_process'

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
  const result = spawnSync('npm', ['run', 'build'], {
    cwd: root,
    env: { ...process.env, VITE_USE_MOCK_DATA: 'true' },
    stdio: 'inherit',
  })

  if (result.status !== 0) {
    throw new Error(`Production build ${number} failed with exit code ${result.status}`)
  }

  const emittedSource = join(dist, 'src')
  if (existsSync(emittedSource)) {
    throw new Error(`Production build ${number} emitted source output at ${emittedSource}`)
  }

  return manifest(dist)
}

const first = await build(1)
const second = await build(2)

if (first.join('\n') !== second.join('\n')) {
  throw new Error('Production build output differs between clean builds')
}

console.log(`Build output contract passed with ${first.length} files`)
