import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, extname, join, relative, resolve } from 'node:path'

const frontendRoot = resolve(process.cwd())
const repositoryRoot = resolve(frontendRoot, '../..')
const output = resolve(repositoryRoot, 'docs/architecture/frontend-inventory.json')
const frontendExtensions = new Set(['.ts', '.vue', '.scss', '.css', '.html', '.json'])

async function filesUnder(directory, accepted) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = join(directory, entry.name)
    if (entry.isDirectory() && !['dist', 'node_modules', 'test-results'].includes(entry.name)) files.push(...await filesUnder(path, accepted))
    if (entry.isFile() && accepted(path)) files.push(path)
  }
  return files.sort()
}

function add(entries, value) {
  if (!entries.includes(value)) entries.push(value)
}

function locations(path, content, matcher, map) {
  for (const match of content.matchAll(matcher)) {
    const line = content.slice(0, match.index).split('\n').length
    map.push({ file: relative(repositoryRoot, path), line, match: match[0].slice(0, 180) })
  }
}

function counts(inventory) {
  return Object.fromEntries(Object.entries(inventory).map(([key, value]) => [key, Array.isArray(value) ? value.length : value]))
}

const frontendFiles = await filesUnder(frontendRoot, path => frontendExtensions.has(extname(path)))
const source = new Map(await Promise.all(frontendFiles.map(async path => [path, await readFile(path, 'utf8')])))
const inventory = {
  schemaVersion: 1,
  generatedBy: 'app/frontend/scripts/inventory-frontend.mjs',
  sourceRoot: 'app/frontend',
  frontendFiles: frontendFiles.map(path => relative(repositoryRoot, path)),
  routes: [],
  navigationDestinations: [],
  apiCalls: [],
  websocketConsumers: [],
  storage: [],
  overlays: [],
  forms: [],
  tables: [],
  destructiveActions: [],
  states: [],
  players: [],
  pwa: [],
  breakpoints: [],
  directDomMutations: [],
  moduleScopeMutableState: [],
  listenersAndTimers: [],
  anyTypes: [],
  nonsemanticActions: [],
  nativeDialogs: [],
  vHtml: [],
  transitionAll: [],
  raw100vh: [],
  potentialUndersizeTargets: [],
}

const routerPath = join(frontendRoot, 'src/router/index.ts')
const router = source.get(routerPath) ?? ''
for (const match of router.matchAll(/path:\s*['"]([^'"]+)['"][\s\S]{0,180}?name:\s*['"]([^'"]+)['"][\s\S]{0,240}?component:\s*([^,\n}]+)/g)) {
  inventory.routes.push({ path: match[1], name: match[2], component: match[3].trim(), file: 'app/frontend/src/router/index.ts' })
}
for (const [path, content] of source) {
  for (const match of content.matchAll(/(?:router\.(?:push|replace)|<RouterLink[^>]+\bto=)\s*\(?\s*['"]([^'"]+)/g)) add(inventory.navigationDestinations, match[1])
  for (const match of content.matchAll(/apiClient\.(get|post|put|patch|delete)\(\s*([`'"])(.*?)\2/g)) {
    inventory.apiCalls.push({ method: match[1].toUpperCase(), path: match[3], source: relative(repositoryRoot, path), auth: 'cookie credentials include via ApiClient', headers: ['Content-Type: application/json'] })
  }
  for (const match of content.matchAll(/fetch\(\s*([`'"])(.*?)\1\s*,?([\s\S]{0,320}?)(?:\}\)|\)\s*;)/g)) {
    inventory.apiCalls.push({ method: /method:\s*['"](\w+)/.exec(match[3])?.[1] ?? 'GET', path: match[2], source: relative(repositoryRoot, path), auth: /credentials:\s*['"]include/.test(match[3]) ? 'cookie credentials include' : 'not statically explicit', headers: [...match[3].matchAll(/['"]([A-Za-z-]+)['"]\s*:/g)].map(item => item[1]) })
  }
  if (/new WebSocket|\.onMessage\(|\.onEvent\(/.test(content)) inventory.websocketConsumers.push(relative(repositoryRoot, path))
  for (const match of content.matchAll(/(?:localStorage|sessionStorage|appStorage)\.(?:getItem|setItem|removeItem|clear|read|write|remove)?\s*\(?\s*['"]([^'"]+)/g)) add(inventory.storage, match[1])
  if (/\b(?:modal|dialog|drawer|sheet|popover|toast|overlay|menu)\b/i.test(content)) inventory.overlays.push(relative(repositoryRoot, path))
  if (/<form\b/i.test(content)) inventory.forms.push(relative(repositoryRoot, path))
  if (/<table\b/i.test(content)) inventory.tables.push(relative(repositoryRoot, path))
  if (/(?:delete|clear|stop|remove|cleanup|logout|unsubscribe)/i.test(content) && /@click|\.post\(|\.delete\(/.test(content)) inventory.destructiveActions.push(relative(repositoryRoot, path))
  if (/(?:loading|empty|error|reconnect|offline)/i.test(content)) inventory.states.push(relative(repositoryRoot, path))
  if (/(?:<video\b|hls\.js|Hls\b|playlist\.m3u8)/i.test(content)) inventory.players.push(relative(repositoryRoot, path))
  if (/(?:registerSW|serviceWorker|beforeinstallprompt|manifest|push)/i.test(content)) inventory.pwa.push(relative(repositoryRoot, path))
  locations(path, content, /@media[^\n{]*\b(?:min|max)-width\s*:\s*[^){]+/g, inventory.breakpoints)
  locations(path, content, /\bdocument\.(?:body|documentElement|createElement|querySelector|getElementById|execCommand)/g, inventory.directDomMutations)
  locations(path, content, /^(?:let|const)\s+\w+\s*=\s*(?:new |\[|\{|null|false|true|\d)/gm, inventory.moduleScopeMutableState)
  locations(path, content, /(?:addEventListener|removeEventListener|setInterval|setTimeout|clearInterval|clearTimeout)\s*\(/g, inventory.listenersAndTimers)
  locations(path, content, /:\s*any(?:\[\])?\b|as\s+any\b/g, inventory.anyTypes)
  locations(path, content, /<(?:div|span|li)[^>]*@click/g, inventory.nonsemanticActions)
  locations(path, content, /\b(?:alert|confirm|prompt)\s*\(/g, inventory.nativeDialogs)
  locations(path, content, /v-html\s*=/g, inventory.vHtml)
  locations(path, content, /transition\s*:\s*all\b/g, inventory.transitionAll)
  locations(path, content, /\b(?:min-)?height\s*:\s*100vh\b/g, inventory.raw100vh)
  locations(path, content, /(?:width|height|min-width|min-height)\s*:\s*(?:[0-3]?\d|40)px/g, inventory.potentialUndersizeTargets)
}

const routeFiles = await filesUnder(join(repositoryRoot, 'app/routes'), path => extname(path) === '.py')
const backendRoutes = []
for (const path of routeFiles) {
  const content = await readFile(path, 'utf8')
  const prefix = /APIRouter\(\s*prefix\s*=\s*['"]([^'"]*)/.exec(content)?.[1] ?? ''
  for (const match of content.matchAll(/@router\.(get|post|put|patch|delete)\(\s*['"]([^'"]*)/g)) backendRoutes.push({ method: match[1].toUpperCase(), path: `${prefix}${match[2]}`, source: relative(repositoryRoot, path) })
}
inventory.backendRoutes = backendRoutes
inventory.counts = counts(inventory)
await mkdir(dirname(output), { recursive: true })
await writeFile(output, `${JSON.stringify(inventory, null, 2)}\n`)
console.log(`Wrote ${relative(repositoryRoot, output)} with ${inventory.frontendFiles.length} frontend files and ${backendRoutes.length} backend routes`)
