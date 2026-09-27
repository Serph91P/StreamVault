import { createHash } from 'node:crypto'
import { copyFile, mkdir, readFile, readdir, realpath, writeFile } from 'node:fs/promises'
import { basename, join, resolve } from 'node:path'

const requiredNames = [
  'foundation-mobile-dark.png',
  'foundation-mobile-light.png',
  'foundation-desktop-dark.png',
  'foundation-desktop-light.png',
]

function parseArguments(argv) {
  const values = new Map()
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]
    const value = argv[index + 1]
    if (!['--source', '--output'].includes(flag) || !value) {
      throw new Error('usage: package-foundation-evidence.mjs --source <playwright-output> --output <delivery-directory>')
    }
    values.set(flag, value)
  }
  if (!values.has('--source') || !values.has('--output')) {
    throw new Error('--source and --output are required; delivery packaging has no default path')
  }
  return { source: resolve(values.get('--source')), output: resolve(values.get('--output')) }
}

async function collect(directory, matches) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await collect(path, matches)
    else if (entry.isFile() && requiredNames.includes(basename(path))) matches.push(path)
  }
}

async function main() {
  const { source, output } = parseArguments(process.argv.slice(2))
  const resolvedSource = await realpath(source)
  if (resolvedSource === output) throw new Error('--source and --output must be different directories')

  const matches = []
  await collect(resolvedSource, matches)
  const byName = new Map(requiredNames.map(name => [name, matches.filter(path => basename(path) === name)]))
  const invalid = [...byName].filter(([, paths]) => paths.length !== 1)
  if (invalid.length) {
    throw new Error(`expected exactly one current capture for each required image; found ${invalid.map(([name, paths]) => `${name}=${paths.length}`).join(', ')}`)
  }

  await mkdir(output, { recursive: true })
  const manifest = []
  for (const name of requiredNames) {
    const sourcePath = byName.get(name)[0]
    const outputPath = join(output, name)
    await copyFile(sourcePath, outputPath)
    const digest = createHash('sha256').update(await readFile(outputPath)).digest('hex')
    manifest.push(`${digest}  ${name}`)
  }
  await writeFile(join(output, 'FOUNDATION-SHA256SUMS'), `${manifest.join('\n')}\n`)
  console.log(`Packaged ${requiredNames.length} foundation captures in ${output}`)
}

main().catch(error => {
  console.error(error instanceof Error ? error.message : error)
  process.exitCode = 1
})
