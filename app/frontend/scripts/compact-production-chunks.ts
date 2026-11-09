import type { Plugin } from 'vite'
import { minify as oxcMinify } from 'rolldown/utils'
import { minify as terserMinify } from 'terser'

// Oxc folds the bundled helpers; Terser then collapses the exposed expressions.
// Vite's final Oxc pass still owns hashing and emitted worker/app artifacts.
export function compactProductionChunks(): Plugin {
  return {
    name: 'streamvault-compact-production-chunks',
    apply: 'build',
    async renderChunk(source, chunk, options) {
      const compact = await oxcMinify(chunk.fileName, source, { compress: true, mangle: true })
      const result = await terserMinify(compact.code, {
        ecma: 2020,
        module: options.format === 'es',
        compress: { passes: 4 },
      })
      return { code: result.code!, map: null }
    },
  }
}
