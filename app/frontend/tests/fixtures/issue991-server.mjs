// Isolated fixture server: actual HTTP requests, synthetic auth/DTOs, no database/providers.
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { resolve, extname } from 'node:path'
import { syntheticReply } from './issue828SyntheticApi.ts'

const root = resolve('dist')
let authenticated = true
let requests = []
const contentTypes = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json' }
createServer(async (request, response) => {
  const path = new URL(request.url, 'http://127.0.0.1').pathname
  const json = (body, status = 200) => {
    response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
    response.end(JSON.stringify(body))
  }
  if (path === '/__fixture/reset' && request.method === 'POST') {
    authenticated = false
    requests = []
    return json({ success: true })
  }
  if (path === '/__fixture/requests') return json(requests)
  const apiRequest = path.startsWith('/api/') || path.startsWith('/auth/') && !request.headers.accept?.includes('text/html')
  if (apiRequest) {
    requests.push({ method: request.method, path, query: new URL(request.url, 'http://127.0.0.1').search })
    if (path === '/auth/check') return json({ authenticated })
    if (path === '/auth/keepalive' && request.method === 'POST') return json({ authenticated })
    if (path === '/auth/logout' && request.method === 'POST') {
      authenticated = false
      return json({ success: true })
    }
    if (path === '/auth/login' && request.method === 'POST') {
      authenticated = true
      return json({ authenticated: true })
    }
    if (path.startsWith('/api/status/') && !authenticated) return json({ detail: 'Synthetic unauthenticated' }, 401)
    const reply = syntheticReply(path, request.method)
    return json(reply.body, reply.status)
  }
  try {
    let file = resolve(root, `.${decodeURIComponent(path)}`)
    if (!file.startsWith(root + '/')) file = resolve(root, 'index.html')
    if (!extname(file)) file = resolve(root, 'index.html')
    const body = await readFile(file)
    response.writeHead(200, { 'Content-Type': contentTypes[extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' })
    response.end(body)
  } catch {
    response.writeHead(404)
    response.end('Missing fixture asset')
  }
}).listen(4189, '127.0.0.1', () => console.log('issue991 REAL fixture listening on 4189'))
