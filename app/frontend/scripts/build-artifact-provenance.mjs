import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { basename, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

export const BUILD_PROVENANCE_FILENAME = '.streamvault-build-provenance.json'
const schema = 1
const modes = new Set(['mock', 'real'])
const sourceInputs = [
  'src',
  'public',
  'index.html',
  'package.json',
  'package-lock.json',
  'tsconfig.json',
  'tsconfig.app.json',
  'tsconfig.node.json',
  'vite.config.ts',
  'scripts/build-artifact-provenance.mjs',
]

function requireMode(mode) {
  if (!modes.has(mode)) throw new Error(`Build mode must be "mock" or "real", received ${JSON.stringify(mode)}`)
  return mode
}

async function filesUnder(root, inputs, excludedBasename) {
  const files = []

  async function visit(path) {
    if (!existsSync(path)) return
    const entries = await readdir(path, { withFileTypes: true })
    for (const entry of entries) {
      const child = join(path, entry.name)
      if (entry.isDirectory()) await visit(child)
      else if (entry.isFile() && entry.name !== excludedBasename) files.push(child)
    }
  }

  for (const input of inputs) {
    const path = join(root, input)
    if (!existsSync(path)) continue
    const entries = await readdir(path, { withFileTypes: true }).catch(() => null)
    if (entries === null) {
      if (basename(path) !== excludedBasename) files.push(path)
    } else {
      await visit(path)
    }
  }

  return files.sort((left, right) => relative(root, left).localeCompare(relative(root, right)))
}

async function digestFiles(root, files) {
  const manifest = []
  for (const path of files) {
    manifest.push([
      relative(root, path).split('\\').join('/'),
      createHash('sha256').update(await readFile(path)).digest('hex'),
    ])
  }
  return {
    sha256: createHash('sha256').update(JSON.stringify(manifest)).digest('hex'),
    fileCount: manifest.length,
  }
}

async function sourceIdentity(root) {
  const files = await filesUnder(root, sourceInputs)
  if (files.length === 0) throw new Error('Build source inputs are missing')
  return digestFiles(root, files)
}

async function artifactIdentity(root) {
  const dist = join(root, 'dist')
  if (!existsSync(dist)) throw new Error(`Build output is missing at ${dist}`)
  const files = await filesUnder(dist, ['.'], BUILD_PROVENANCE_FILENAME)
  if (files.length === 0) throw new Error('Build output contains no reusable files')
  return digestFiles(dist, files)
}

export async function recordBuildProvenance(root, mode) {
  requireMode(mode)
  const [source, artifact] = await Promise.all([sourceIdentity(root), artifactIdentity(root)])
  const provenance = {
    schema,
    mode,
    sourceSha256: source.sha256,
    sourceFileCount: source.fileCount,
    artifactSha256: artifact.sha256,
    fileCount: artifact.fileCount,
  }
  await writeFile(join(root, 'dist', BUILD_PROVENANCE_FILENAME), `${JSON.stringify(provenance, null, 2)}\n`)
  return provenance
}

export async function verifyBuildProvenance(root, mode) {
  requireMode(mode)
  const marker = join(root, 'dist', BUILD_PROVENANCE_FILENAME)
  if (!existsSync(marker)) throw new Error(`Verified build provenance is missing at ${marker}`)

  let provenance
  try {
    provenance = JSON.parse(await readFile(marker, 'utf8'))
  } catch (error) {
    throw new Error(`Verified build provenance is not valid JSON: ${error instanceof Error ? error.message : String(error)}`)
  }
  if (provenance.schema !== schema) throw new Error(`Verified build provenance schema mismatch: expected ${schema}`)
  if (provenance.mode !== mode) throw new Error(`Verified build mode mismatch: expected ${mode}, found ${String(provenance.mode)}`)

  const [source, artifact] = await Promise.all([sourceIdentity(root), artifactIdentity(root)])
  if (provenance.sourceSha256 !== source.sha256 || provenance.sourceFileCount !== source.fileCount) {
    throw new Error('Verified build source bytes changed after the artifact was created')
  }
  if (provenance.artifactSha256 !== artifact.sha256 || provenance.fileCount !== artifact.fileCount) {
    throw new Error('Verified build artifact bytes changed after provenance was recorded')
  }
  return provenance
}

export async function buildVerifiedArtifact(root, mode) {
  requireMode(mode)
  await rm(join(root, 'dist'), { recursive: true, force: true })
  const result = spawnSync('npm', ['run', 'build'], {
    cwd: root,
    env: { ...process.env, VITE_USE_MOCK_DATA: mode === 'mock' ? 'true' : 'false' },
    stdio: 'inherit',
  })
  if (result.status !== 0) throw new Error(`${mode} build failed with exit code ${result.status ?? 'unknown'}`)
  return recordBuildProvenance(root, mode)
}

async function main() {
  const [command, modeFlag, mode] = process.argv.slice(2)
  if (modeFlag !== '--mode' || process.argv.length !== 5) {
    throw new Error('Usage: build-artifact-provenance.mjs <build|verify> --mode <mock|real>')
  }
  const root = process.cwd()
  if (command === 'build') {
    const provenance = await buildVerifiedArtifact(root, mode)
    console.log(`Recorded ${mode} build provenance ${provenance.artifactSha256} (${provenance.fileCount} files)`)
  } else if (command === 'verify') {
    const provenance = await verifyBuildProvenance(root, mode)
    console.log(`Verified ${mode} build provenance ${provenance.artifactSha256} (${provenance.fileCount} files)`)
  } else {
    throw new Error(`Unknown build provenance command: ${String(command)}`)
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main()
}
