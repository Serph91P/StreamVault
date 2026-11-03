// @vitest-environment node
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'
import config from '../../vite.config'

const hostModule = fileURLToPath(new URL('../../src/components/settings/SettingsPanelHost.vue', import.meta.url))

function emittedLoader(bundle: Record<string, unknown>): string {
  const plugin = config.plugins?.flat().find(item => item && 'name' in item && item.name === 'streamvault-retryable-settings-panel-host')
  if (!plugin || !('generateBundle' in plugin)) throw new Error('Settings loader plugin is missing')
  const hook = plugin.generateBundle
  const handler = typeof hook === 'function' ? hook : hook?.handler
  if (!handler) throw new Error('Settings loader build hook is missing')
  const emitFile = vi.fn()
  Reflect.apply(handler, { emitFile, error: (message: string) => { throw new Error(message) } }, [{}, bundle, false])
  return emitFile.mock.calls[0][0].source as string
}

function chunk(css: string[], imports: string[] = [], modules = {}, dynamicImports: string[] = []) {
  return { type: 'chunk', fileName: 'assets/SettingsPanelHost.js', modules, imports, dynamicImports,
    viteMetadata: { importedCss: new Set(css) } }
}

describe('retryable settings stylesheet dependencies', () => {
  it('includes all transitive static CSS once without pulling in dynamic chunks', () => {
    const bundle = {
      'assets/SettingsPanelHost.js': chunk(['assets/host.css'], ['assets/recording.js'], { [hostModule]: {} }, ['assets/lazy.js']),
      'assets/recording.js': chunk(['assets/recording.css'], ['assets/base.js']),
      'assets/base.js': chunk(['assets/base.css', 'assets/host.css'], ['assets/recording.js']),
      'assets/lazy.js': chunk(['assets/lazy.css']),
    }
    const source = emittedLoader(bundle)
    const css = JSON.parse(source.match(/panelCssUrls=(\[[^;]+\]);/)![1])
    expect(css).toEqual(['./base.css', './host.css', './recording.css'])
    expect(css).not.toContain('./lazy.css')
  })

  it('accepts a host whose CSS is entirely extracted into a static dependency', () => {
    const source = emittedLoader({
      'assets/SettingsPanelHost.js': chunk([], ['assets/shared.js'], { [hostModule]: {} }),
      'assets/shared.js': chunk(['assets/shared.css']),
    })
    expect(source).toContain('panelCssUrls=["./shared.css"]')
  })
})
