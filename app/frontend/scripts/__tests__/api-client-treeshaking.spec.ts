// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'
import { rolldown } from 'rolldown'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'

const sourcePath = resolve(import.meta.dirname, '../../src/services/api-real.ts')

// Bundle the actual module, not a rewritten copy. Only transitive router/storage
// initialization is external: these tests isolate the client construction itself.
async function bundleConsumer(exports: string) {
  const entry = 'virtual:api-client-consumer'
  const bundle = await rolldown({
    input: entry,
    external: ['@/router', '@/services/storage'],
    plugins: [{
      name: 'actual-api-client-consumer',
      resolveId(id) { if (id === entry) return id },
      load(id) { if (id === entry) return `export { ${exports} } from ${JSON.stringify(sourcePath)}` },
    }],
  })
  try {
    const output = await bundle.generate({ format: 'cjs', minify: true })
    return output.output.filter(item => item.type === 'chunk').map(item => item.code).join('\n')
  } finally {
    await bundle.close()
  }
}

function executeConsumer(code: string) {
  const fetch = vi.fn()
  const push = vi.fn(() => Promise.resolve())
  const clearSessionToken = vi.fn()
  const clearSessionStorage = vi.fn()
  const module = { exports: {} as Record<string, any> }
  const require = (id: string) => {
    if (id === '@/router') return { push }
    if (id === '@/services/storage') return { appStorage: { clearSessionToken, clearSessionStorage } }
    throw new Error(`Unexpected external module: ${id}`)
  }
  runInNewContext(code, { module, exports: module.exports, require, fetch, URL, URLSearchParams, console })
  return { api: module.exports, fetch, push, clearSessionToken, clearSessionStorage }
}

function expectNoConstructionEffects(consumer: ReturnType<typeof executeConsumer>) {
  expect(consumer.fetch).not.toHaveBeenCalled()
  expect(consumer.push).not.toHaveBeenCalled()
  expect(consumer.clearSessionToken).not.toHaveBeenCalled()
  expect(consumer.clearSessionStorage).not.toHaveBeenCalled()
}

describe('actual ApiClient construction and tree shaking', () => {
  it('keeps the purity premise: no base class, decorators, fields, static blocks or computed initialization', () => {
    const source = ts.createSourceFile(sourcePath, readFileSync(sourcePath, 'utf8'), ts.ScriptTarget.Latest, true)
    const client = source.statements.find((node): node is ts.ClassDeclaration => ts.isClassDeclaration(node) && node.name?.text === 'ApiClient')!
    expect(client).toBeDefined()
    expect(client.heritageClauses).toBeUndefined()
    expect(ts.getDecorators(client)).toBeUndefined()
    const constructor = client.members.find(ts.isConstructorDeclaration)!
    expect(constructor.parameters).toHaveLength(0)
    expect(constructor.body!.statements).toHaveLength(0)
    for (const member of client.members) {
      expect(ts.isConstructorDeclaration(member) || ts.isMethodDeclaration(member)).toBe(true)
      expect(member.name && ts.isComputedPropertyName(member.name)).toBeFalsy()
      expect(ts.canHaveDecorators(member) ? ts.getDecorators(member) : undefined).toBeUndefined()
    }
  })

  it('eliminates unused real request/refresh code for an actual errors-only consumer without losing error behavior', async () => {
    const code = await bundleConsumer('ApiRequestError, isApiRequestError')
    expect(code).not.toContain('/auth/refresh')
    expect(code).not.toContain('Session expired - redirecting to login')
    const consumer = executeConsumer(code)
    const { ApiRequestError, isApiRequestError } = consumer.api
    const detail = { reason: 'Synthetic failure' }
    const error = new ApiRequestError('Synthetic failure', 'http_error', 503, detail)
    expect(error).toMatchObject({ name: 'ApiRequestError', message: 'Synthetic failure', code: 'http_error', status: 503, detail })
    expect(isApiRequestError(error)).toBe(true)
    expect(isApiRequestError(new Error('unrelated'))).toBe(false)
    expectNoConstructionEffects(consumer)
  })

  it('retains and executes genuine request/refresh/retry code for live singleton and class consumers', async () => {
    const code = await bundleConsumer('default, ApiClient')
    expect(code).toContain('/auth/refresh')
    expect(code).toContain('Session expired - redirecting to login')
    const consumer = executeConsumer(code)
    const singleton = consumer.api.default
    expect(singleton).toBeInstanceOf(consumer.api.ApiClient)
    const client = new consumer.api.ApiClient()
    expect(client).not.toBe(singleton)
    expectNoConstructionEffects(consumer)
    for (const instance of [singleton, client]) {
      consumer.fetch.mockReset()
      consumer.fetch
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockResolvedValueOnce(new Response(null, { status: 204 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ result: 'real-client' }), {
          headers: { 'content-type': 'application/json' },
        }))
      await expect(instance.get('/api/synthetic')).resolves.toEqual({ result: 'real-client' })
      expect(consumer.fetch).toHaveBeenNthCalledWith(1, '/api/synthetic', expect.objectContaining({ method: 'GET', credentials: 'include' }))
      expect(consumer.fetch).toHaveBeenNthCalledWith(2, '/auth/refresh', { method: 'POST', credentials: 'include' })
      expect(consumer.fetch).toHaveBeenNthCalledWith(3, '/api/synthetic', expect.objectContaining({ method: 'GET', credentials: 'include' }))
      expect(consumer.fetch).toHaveBeenCalledTimes(3)
    }
    expect(consumer.push).not.toHaveBeenCalled()
    expect(consumer.clearSessionToken).not.toHaveBeenCalled()
    expect(consumer.clearSessionStorage).not.toHaveBeenCalled()
  })
})
