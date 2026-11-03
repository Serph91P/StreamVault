import { describe, expect, it } from 'vitest'
import source from '../StreamersView.vue?raw'
import tokens from '@/styles/design.tokens.json'


function relativeLuminance(hex: string) {
  const channels = hex.match(/[a-f0-9]{2}/gi)!.map(channel => Number.parseInt(channel, 16) / 255)
  const linear = channels.map(channel => (
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ))
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
}

function contrast(foreground: string, background: string) {
  const [lighter, darker] = [relativeLuminance(foreground), relativeLuminance(background)].sort((a, b) => b - a)
  return (lighter + 0.05) / (darker + 0.05)
}

describe('StreamersView active filter badge contrast', () => {
  it('keeps active filters and count badges legible on opaque neutral surfaces in both themes', () => {
    const activeRule = source.match(/&\.active\s*\{([\s\S]*?)\n  \}/)?.[1]
    const badgeRule = activeRule?.match(/\.tab-badge\s*\{([\s\S]*?)\n    \}/)?.[1]

    expect(activeRule).toContain('background: var(--sv-sem-surface-selected);')
    expect(activeRule).toContain('color: var(--sv-sem-text-primary);')
    expect(badgeRule).toContain('background: var(--sv-sem-surface-panel);')
    expect(badgeRule).toContain('color: var(--sv-sem-text-primary);')
    expect(badgeRule).not.toMatch(/rgba\s*\(/)
    expect(badgeRule).not.toMatch(/opacity\s*:/)
    const color = (reference: string) => tokens.foundation.color[
      reference.replace('{foundation.color.', '').replace('}', '') as keyof typeof tokens.foundation.color
    ]
    for (const theme of [tokens.semanticDark, tokens.semanticLight]) {
      for (const surface of [theme.surface.selected, theme.surface.panel]) {
        expect(contrast(color(theme.text.primary), color(surface))).toBeGreaterThanOrEqual(4.5)
      }
    }
  })
})
