import { describe, expect, it } from 'vitest'
import videoPlayerViewSource from '../VideoPlayerView.vue?raw'

describe('VideoPlayerView chapter navigation', () => {
  it('renders chapters as native buttons with stable accessible names', () => {
    const chapterMarkup = videoPlayerViewSource.match(/<div class="chapters-list">([\s\S]*?)<\/div>\s*<\/GlassCard>/)?.[1]

    expect(chapterMarkup).toBeDefined()
    expect(chapterMarkup).toContain('<button')
    expect(chapterMarkup).toContain('type="button"')
    expect(chapterMarkup).toContain(':aria-label="chapterAccessibleName(chapter)"')
    expect(chapterMarkup).not.toMatch(/<div\s+v-for=/)
  })
})
