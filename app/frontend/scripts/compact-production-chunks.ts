import type { Plugin } from 'vite'
import { minify as oxcMinify } from 'rolldown/utils'
import { minify as swcMinify } from '@swc/core'

// Native passes avoid JS compressor CPU contention during production builds.
// Vite's final Oxc pass still owns emitted code, hashing and worker artifacts.
export function compactProductionChunks(): Plugin {
  return {
    name: 'streamvault-compact-production-chunks',
    apply: 'build',
    async renderChunk(source, chunk, options) {
      const compact = await oxcMinify(chunk.fileName, source, { compress: true, mangle: true })
      const result = await swcMinify(compact.code, {
        ecma: 2020, module: options.format === 'es',
        compress: { passes: 3 }, mangle: true, format: { comments: 'some' },
      })
      return { code: result.code, map: null }
    },
  }
}
