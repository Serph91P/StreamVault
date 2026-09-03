import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StreamCard from '../StreamCard.vue'
import streamCardSource from '../StreamCard.vue?raw'

const stream = {
  id: 7,
  streamer_id: 42,
  title: 'A recorded stream',
  category_name: 'Just Chatting',
  started_at: '2026-09-03T10:00:00Z',
  ended_at: '2026-09-03T11:00:00Z',
}

describe('StreamCard expansion', () => {
  it('does not expand when its row or body is clicked', async () => {
    const wrapper = mount(StreamCard, { props: { stream } })

    await wrapper.get('.stream-compact').trigger('click')

    expect(wrapper.find('.stream-expanded').exists()).toBe(false)
  })

  it('uses one persistent native button with a stable expanded relationship', async () => {
    const wrapper = mount(StreamCard, { props: { stream } })
    const buttons = wrapper.findAll('button.expand-btn')
    expect(buttons).toHaveLength(1)

    const button = buttons[0]
    const controlsBefore = button.attributes('aria-controls')
    const expandedBefore = button.attributes('aria-expanded')

    await button.trigger('click')

    const controlsAfter = button.attributes('aria-controls')
    const panel = wrapper.get('.stream-expanded')
    expect({
      nativeButton: button.element.tagName === 'BUTTON',
      expandedBefore,
      expandedAfter: button.attributes('aria-expanded'),
      controlsStable: Boolean(controlsBefore) && controlsBefore === controlsAfter,
      controlledPanel: Boolean(controlsAfter) && panel.attributes('id') === controlsAfter,
      regionRole: panel.attributes('role'),
    }).toEqual({
      nativeButton: true,
      expandedBefore: 'false',
      expandedAfter: 'true',
      controlsStable: true,
      controlledPanel: true,
      regionRole: 'region',
    })
  })

  it('renders the GlassCard as an article with a persistent 44px expand control', () => {
    const wrapper = mount(StreamCard, { props: { stream } })

    expect(wrapper.get('.stream-card').element.tagName).toBe('ARTICLE')
    expect(streamCardSource).toMatch(/\.expand-btn\s*\{[\s\S]*?width:\s*44px;[\s\S]*?height:\s*44px;/)
    expect(streamCardSource).not.toMatch(/Tap to expand|\.expand-btn\s*\{\s*display:\s*none;/)
  })

  it('uses native button activation without duplicate Enter or Space handlers', () => {
    const wrapper = mount(StreamCard, { props: { stream } })
    const button = wrapper.get('button.expand-btn')

    expect(button.attributes('type')).toBe('button')
    expect(streamCardSource).not.toMatch(/@key(?:down|up)(?:\.enter|\.space)[^=]*="toggleExpand"/)
    expect(streamCardSource).toMatch(/@keydown\.enter\.stop/)
    expect(streamCardSource).toMatch(/@keydown\.space\.stop/)
    expect(streamCardSource).not.toMatch(/stream-compact[^>]*@click/)
  })

  it('marks vertical card and compact-row surfaces as pan-y', () => {
    expect(streamCardSource).toMatch(/\.stream-card\s*\{[\s\S]*?touch-action:\s*pan-y;/)
    expect(streamCardSource).toMatch(/\.stream-compact\s*\{[\s\S]*?touch-action:\s*pan-y;/)
    expect(streamCardSource).not.toMatch(/\.stream-compact\s*\{[^}]*cursor:\s*pointer;/)
  })
})
