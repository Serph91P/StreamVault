import type { Plugin } from 'vite'
import { minify as oxcMinify } from 'rolldown/utils'

// Fold bundled helpers before Vite's parallel Terser pass and final Oxc output.
export function compactProductionChunks(): Plugin {
  return {
    name: 'streamvault-compact-production-chunks',
    apply: 'build',
    async renderChunk(source, chunk) {
      const compact = await oxcMinify(chunk.fileName, source, { compress: true, mangle: true })
      return { code: compact.code, map: null }
    },
  }
}
