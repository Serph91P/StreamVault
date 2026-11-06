import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import originals from '../../tests/fixtures/player-control-originals.json'

const asset = resolve(import.meta.dirname, '../../src/assets/player-controls.svg')
const components = ['../../src/components/VideoPlayer.vue', '../../src/views/VideoPlayerView.vue']

describe('cacheable player control artwork', () => {
  it('preserves every original geometry attribute', () => {
    const parser = new DOMParser()
    const document = parser.parseFromString(readFileSync(asset, 'utf8'), 'image/svg+xml')
    const shapes = (element: Element) => Array.from(element.children, child => ({
      tag: child.tagName,
      attributes: Object.fromEntries(Array.from(child.attributes, attribute => [attribute.name, attribute.value])),
    }))
    for (const glyph of originals) {
      const original = parser.parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${glyph.geometry}</svg>`, 'image/svg+xml')
      const actual = document.getElementById(glyph.id)
      expect(actual, glyph.id).not.toBeNull()
      expect(shapes(actual!), glyph.id).toEqual(shapes(original.documentElement))
    }
  })

  it('ships the static glyphs as a same-origin SVG resource', () => {
    expect(existsSync(asset)).toBe(true)
    const document = new DOMParser().parseFromString(readFileSync(asset, 'utf8'), 'image/svg+xml')
    expect(document.querySelector('parsererror')).toBeNull()
    expect(document.querySelectorAll('script, foreignObject, image')).toHaveLength(0)
    expect(document.querySelectorAll('g[id]')).toHaveLength(14)
  })

  it('resolves every player glyph without embedding geometry in JavaScript', () => {
    const references = components.flatMap(component =>
      [...readFileSync(fileURLToPath(new URL(component, import.meta.url)), 'utf8')
        .matchAll(/href="\.\.\/assets\/player-controls\.svg\?no-inline#([\w-]+)"/g)].map(match => match[1]))
    expect(references).toHaveLength(15)
    const document = new DOMParser().parseFromString(readFileSync(asset, 'utf8'), 'image/svg+xml')
    for (const id of references) expect(document.getElementById(id), id).not.toBeNull()
  })
})
