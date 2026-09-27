import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

export const requiredStaticAssets = [
  'favicon.ico',
  'android-icon-192x192.png',
  'icon-512x512.png',
  'maskable-icon-192x192.png',
  'maskable-icon-512x512.png',
]

export function precacheEntries(source) {
  return [...source.matchAll(/\{url:"([^"]+)",revision:(?:"([^"]+)"|(null))\}/g)]
    .map(([, url, revision, nullRevision]) => ({ url, revision: revision ?? nullRevision }))
}

export function assertPrecacheIntegrity(source, requiredAssets = requiredStaticAssets) {
  const entries = precacheEntries(source)
  const seen = new Map()
  const duplicates = []

  for (const entry of entries) {
    const previous = seen.get(entry.url)
    if (previous !== undefined) duplicates.push(`${entry.url} (${previous} and ${entry.revision})`)
    seen.set(entry.url, entry.revision)
  }
  if (duplicates.length > 0) throw new Error(`Duplicate precache URLs: ${duplicates.join(', ')}`)

  const missing = requiredAssets.filter((asset) => !seen.has(asset))
  if (missing.length > 0) throw new Error(`Missing required precache assets: ${missing.join(', ')}`)

  return entries
}

export function assertSamePrecacheResources(referenceSource, candidateSource) {
  const normalize = (source) => {
    const map = new Map()
    for (const { url, revision } of precacheEntries(source)) {
      const previous = map.get(url)
      if (previous !== undefined && previous !== revision) throw new Error(`Conflicting precache revision: ${url}`)
      map.set(url, revision)
    }
    return map
  }
  const reference = normalize(referenceSource)
  const candidate = normalize(candidateSource)
  if (reference.size !== candidate.size) throw new Error(`Precache resource count changed: ${reference.size} to ${candidate.size}`)
  for (const [url, revision] of reference) {
    if (candidate.get(url) !== revision) throw new Error(`Precache resource changed or missing: ${url}`)
  }
}

export async function checkPrecacheIntegrity(swPath = resolve(process.cwd(), 'dist/sw.js'), referencePath) {
  const source = await readFile(swPath, 'utf8')
  const entries = assertPrecacheIntegrity(source)
  if (referencePath) assertSamePrecacheResources(await readFile(referencePath, 'utf8'), source)
  console.log(`Precache integrity passed with ${entries.length} unique entries`)
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const swIndex = process.argv.indexOf('--sw')
  const referenceIndex = process.argv.indexOf('--reference')
  const swPath = swIndex >= 0 ? resolve(process.argv[swIndex + 1]) : undefined
  const referencePath = referenceIndex >= 0 ? resolve(process.argv[referenceIndex + 1]) : undefined
  try {
    await checkPrecacheIntegrity(swPath, referencePath)
  } catch (error) {
    console.error(error instanceof Error ? error.message : error)
    process.exitCode = 1
  }
}
