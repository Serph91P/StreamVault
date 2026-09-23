import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { createServer } from 'node:http'
import { extname, resolve, sep } from 'node:path'

const root = resolve(process.env.LIGHTHOUSE_DIST_DIR ?? 'dist')
const host = process.env.LIGHTHOUSE_HOST ?? '127.0.0.1'
const port = Number(process.env.LIGHTHOUSE_PORT ?? '4180')
const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
}

function fileForRequest(url) {
  const pathname = decodeURIComponent(new URL(url, `http://${host}`).pathname)
  const requested = resolve(root, `.${pathname}`)
  if (requested !== root && !requested.startsWith(`${root}${sep}`)) return null
  return requested
}

const mockAuthResponses = {
  '/auth/check': { authenticated: true },
  '/auth/keepalive': { success: true },
  '/auth/setup': { setup_required: false, welcome_completed: true },
}

const server = createServer(async (request, response) => {
  const pathname = new URL(request.url ?? '/', `http://${host}`).pathname
  const mockAuth = mockAuthResponses[pathname]
  if (mockAuth) {
    response.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
    response.end(`${JSON.stringify(mockAuth)}\n`)
    return
  }

  const requested = fileForRequest(request.url ?? '/')
  const fallback = resolve(root, 'index.html')
  try {
    const candidate = requested && await stat(requested).then(entry => entry.isFile() ? requested : fallback).catch(() => fallback)
    const file = candidate ?? fallback
    response.writeHead(200, { 'content-type': contentTypes[extname(file)] ?? 'application/octet-stream' })
    createReadStream(file).pipe(response)
  } catch {
    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' })
    response.end('Not found')
  }
})

server.listen(port, host)
