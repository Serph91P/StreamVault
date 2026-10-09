import { ESLint } from 'eslint'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(import.meta.dirname, '..', '..')
const eslint = new ESLint({ cwd: frontendRoot })

async function rulesFor(code: string, file: string) {
  const [result] = await eslint.lintText(code, { filePath: resolve(frontendRoot, file) })
  return result.messages.map(({ ruleId, severity }) => ({ ruleId, severity }))
}

describe('ESLint flat config compatibility', () => {
  it.each(['fixture.ts', 'fixture.mts', 'fixture.tsx'])(
    'keeps recommended TypeScript and project rules for %s',
    async (file) => {
      await expect(rulesFor('const unused: any = 1\n', file)).resolves.toEqual([
        { ruleId: '@typescript-eslint/no-unused-vars', severity: 2 },
        { ruleId: '@typescript-eslint/no-explicit-any', severity: 1 },
      ])
    },
  )

  it('parses Vue script setup with TypeScript and keeps essential Vue rules', async () => {
    const code = `<template><div id="a" id="b">{{ label }}</div></template>
<script setup lang="ts">
const label: any = 'fixture'
const unused = 1
</script>
`
    await expect(rulesFor(code, 'fixture.vue')).resolves.toEqual([
      { ruleId: 'vue/no-parsing-error', severity: 2 },
      { ruleId: 'vue/no-duplicate-attributes', severity: 2 },
      { ruleId: '@typescript-eslint/no-explicit-any', severity: 1 },
      { ruleId: '@typescript-eslint/no-unused-vars', severity: 2 },
    ])
  })

  it('preserves JavaScript linting', async () => {
    await expect(rulesFor('const unused = 1\n', 'fixture.js')).resolves.toEqual([
      { ruleId: '@typescript-eslint/no-unused-vars', severity: 2 },
    ])
  })

  it.each([
    'dist/ignored.ts',
    'dist-ssr/ignored.ts',
    'coverage/ignored.ts',
    'public/ignored.ts',
    'node_modules/example/ignored.ts',
    'src/ignored.d.ts',
  ])('preserves the global ignore for %s', async (file) => {
    await expect(rulesFor('const unused: any = 1\n', file)).resolves.toEqual([
      { ruleId: null, severity: 1 },
    ])
  })

  it('accepts a clean TypeScript module', async () => {
    await expect(rulesFor('export const answer: number = 42\n', 'fixture.ts')).resolves.toEqual([])
  })
})