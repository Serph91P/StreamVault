import { describe, expect, it } from 'vitest'
import source from '../StreamersView.vue?raw'

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
  it('uses an opaque high-contrast semantic token behind the small white badge text', () => {
    const activeRule = source.match(/&\.active\s*\{([\s\S]*?)\n  \}/)?.[1]
    const badgeRule = activeRule?.match(/\.tab-badge\s*\{([\s\S]*?)\n    \}/)?.[1]

    expect(activeRule).toContain('background: v.$primary-800;')
    expect(badgeRule).toContain('background: v.$primary-900;')
    expect(badgeRule).toContain('color: white;')
    expect(badgeRule).not.toMatch(/rgba\s*\(/)
    expect(badgeRule).not.toMatch(/opacity\s*:/)
    expect(contrast('ffffff', '134e4a')).toBeGreaterThanOrEqual(4.5)
  })
})
