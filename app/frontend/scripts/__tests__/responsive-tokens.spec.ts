import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(import.meta.dirname, '..', '..')

describe('responsive token generator', () => {
  it('keeps the generated TypeScript and Sass owners in parity with the canonical source', async () => {
    const source = await readFile(resolve(frontendRoot, 'src/styles/responsive.tokens.json'), 'utf8')
    const tokens = JSON.parse(source) as { breakpoints: Record<string, number>, queries: Record<string, string> }
    const generatedTypeScript = await readFile(resolve(frontendRoot, 'src/composables/layoutQueries.generated.ts'), 'utf8')
    const generatedSass = await readFile(resolve(frontendRoot, 'src/styles/_responsive.generated.scss'), 'utf8')

    expect(generatedTypeScript).toContain('shell: \'(max-width: 1023.98px)\'')
    expect(generatedTypeScript).toContain('player: \'(max-width: 767px)\'')
    expect(generatedSass).toContain("'md': 768px")
    expect(generatedSass).toContain("'lg': 1024px")
    expect(tokens.breakpoints.md).toBe(768)
    expect(tokens.breakpoints.lg).toBe(1024)
  })
})
