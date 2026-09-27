import { gzipSync } from 'node:zlib'
import { readdir, readFile, stat, writeFile } from 'node:fs/promises'
import { join, relative, resolve } from 'node:path'

const argument = name => {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}
const frontendRoot = resolve(import.meta.dirname, '..')
const dist = resolve(argument('--dist') || resolve(frontendRoot, 'dist'))
const HLS_WORKER_PATTERN = /^assets\/hls\.worker-[A-Za-z0-9_-]+\.js$/

async function installedHlsVersion() {
  const lock = JSON.parse(await readFile(resolve(frontendRoot, 'package-lock.json'), 'utf8'))
  return lock.packages?.['node_modules/hls.js']?.version ?? null
}

async function collect(directory) {
  const files = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) files.push(...await collect(path))
    else if (entry.isFile()) {
      const content = await readFile(path)
      files.push({ path: relative(dist, path), bytes: (await stat(path)).size, gzipBytes: gzipSync(content).length })
    }
  }
  return files.sort((a, b) => a.path.localeCompare(b.path))
}

export async function measureBuildOutput(directory = dist) {
  const files = await collect(directory)
  const select = extension => files.filter(file => file.path.endsWith(extension))
  const sum = (rows, field) => rows.reduce((total, row) => total + row[field], 0)
  const js = select('.js')
  const css = select('.css')
  const sw = files.find(file => file.path === 'sw.js')
  const workers = js.filter(file => HLS_WORKER_PATTERN.test(file.path))
  const workerBytes = sum(workers, 'bytes')
  const workerGzipBytes = sum(workers, 'gzipBytes')
  const swSource = sw ? await readFile(join(directory, sw.path), 'utf8') : ''
  return {
    toolchain: { node: process.version, vite: '8.3.0', measurement: 'raw and node:zlib gzip bytes' },
    files: files.length,
    jsBytes: sum(js, 'bytes'),
    jsGzipBytes: sum(js, 'gzipBytes'),
    cssBytes: sum(css, 'bytes'),
    cssGzipBytes: sum(css, 'gzipBytes'),
    totalBytes: sum(files, 'bytes'),
    precacheEntries: (swSource.match(/\{url:/g) || []).length,
    largestJsBytes: Math.max(0, ...js.map(file => file.bytes)),
    largestCssBytes: Math.max(0, ...css.map(file => file.bytes)),
    applicationJsBytes: sum(js, 'bytes') - workerBytes,
    applicationJsGzipBytes: sum(js, 'gzipBytes') - workerGzipBytes,
    applicationTotalBytes: sum(files, 'bytes') - workerBytes,
    hlsWorker: {
      count: workers.length,
      path: workers.length === 1 ? workers[0].path : null,
      bytes: workerBytes,
      gzipBytes: workerGzipBytes,
      packageVersion: await installedHlsVersion(),
    },
  }
}

export function assertWithinBudgets(metrics, budgetDocument) {
  const budgets = budgetDocument.budgets ?? budgetDocument
  const workerAllowance = budgetDocument.hlsWorkerAllowance
  let checkedMetrics = metrics

  if (workerAllowance) {
    const worker = metrics.hlsWorker
    const applicationJsBytes = metrics.jsBytes - (worker?.bytes ?? 0)
    const applicationJsGzipBytes = metrics.jsGzipBytes - (worker?.gzipBytes ?? 0)
    const applicationTotalBytes = metrics.totalBytes - (worker?.bytes ?? 0)
    const invalid = []
    if (!worker || worker.count !== 1 || !worker.path || !HLS_WORKER_PATTERN.test(worker.path)) invalid.push('exactly one hashed same-origin artifact is required')
    if (!Number.isFinite(worker?.bytes) || worker.bytes < 1 || worker.bytes > workerAllowance.bytes) invalid.push(`raw bytes ${worker?.bytes} exceed ${workerAllowance.bytes}`)
    if (!Number.isFinite(worker?.gzipBytes) || worker.gzipBytes < 1 || worker.gzipBytes > workerAllowance.gzipBytes) invalid.push(`gzip bytes ${worker?.gzipBytes} exceed ${workerAllowance.gzipBytes}`)
    if (worker?.packageVersion !== workerAllowance.packageVersion) invalid.push(`package version ${worker?.packageVersion} does not match ${workerAllowance.packageVersion}`)
    if (applicationJsBytes > budgets.jsBytes) invalid.push(`applicationJsBytes ${applicationJsBytes} > ${budgets.jsBytes}`)
    if (applicationJsGzipBytes > budgets.jsGzipBytes) invalid.push(`applicationJsGzipBytes ${applicationJsGzipBytes} > ${budgets.jsGzipBytes}`)
    if (applicationTotalBytes > budgets.totalBytes) invalid.push(`applicationTotalBytes ${applicationTotalBytes} > ${budgets.totalBytes}`)
    if (metrics.jsBytes > budgets.jsBytes + workerAllowance.bytes) invalid.push('aggregate jsBytes exceed the bounded total')
    if (metrics.jsGzipBytes > budgets.jsGzipBytes + workerAllowance.gzipBytes) invalid.push('aggregate jsGzipBytes exceed the bounded total')
    if (metrics.totalBytes > budgets.totalBytes + workerAllowance.bytes) invalid.push('aggregate totalBytes exceed the bounded total')
    if (invalid.length) throw new Error(`HLS worker budget invalid\n${invalid.join('\n')}`)
    checkedMetrics = {
      ...metrics,
      applicationJsBytes,
      applicationJsGzipBytes,
      applicationTotalBytes,
    }
  }

  const budgetValue = name => {
    if (!workerAllowance) return checkedMetrics[name]
    if (name === 'jsBytes') return checkedMetrics.applicationJsBytes
    if (name === 'jsGzipBytes') return checkedMetrics.applicationJsGzipBytes
    if (name === 'totalBytes') return checkedMetrics.applicationTotalBytes
    return checkedMetrics[name]
  }
  const exceeded = Object.entries(budgets)
    .filter(([name, maximum]) => typeof maximum === 'number' && budgetValue(name) > maximum)
    .map(([name, maximum]) => `${name}: ${budgetValue(name)} > ${maximum}`)
  if (exceeded.length) throw new Error(`build output budget exceeded\n${exceeded.join('\n')}`)
  return checkedMetrics
}

const fixturePath = argument('--fixture')
const metrics = fixturePath ? JSON.parse(await readFile(resolve(fixturePath), 'utf8')) : await measureBuildOutput()
const recordPath = argument('--record')
if (recordPath) await writeFile(resolve(recordPath), `${JSON.stringify(metrics, null, 2)}\n`)
const budgetPath = argument('--budget')
const reportedMetrics = budgetPath
  ? assertWithinBudgets(metrics, JSON.parse(await readFile(resolve(budgetPath), 'utf8')))
  : metrics
console.log(JSON.stringify(reportedMetrics, null, 2))
