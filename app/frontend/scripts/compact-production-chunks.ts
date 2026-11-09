import type { Plugin } from 'vite'
import { minify as swcMinify } from '@swc/core'
import { minify as terserMinify } from 'terser'

// Native compression does the expensive folding; one Terser pass improves gzip.
// Vite's final Oxc pass still owns emitted code, hashing and worker artifacts.
export function compactProductionChunks(): Plugin {
  return {
    name: 'streamvault-compact-production-chunks',
    apply: 'build',
    async renderChunk(source, _chunk, options) {
      const module = options.format === 'es'
      const compact = await swcMinify(source, {
        ecma: 2020, module, compress: { passes: 2 }, mangle: true,
        format: { comments: 'some' },
      })
      const result = await terserMinify(compact.code, {
        ecma: 2020, module, compress: { passes: 1 }, mangle: false,
      })
      return { code: result.code!, map: null }
    },
  }
}
