import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Stream } from '@/types/streams'
import StreamCard from '../StreamCard.vue'
import streamCardSource from '../StreamCard.vue?raw'

const stream: Stream = {
  id: 7,
  streamer_id: 42,
  title: 'A recorded stream',
  category_name: 'Just Chatting',
  started_at: '2026-09-03T10:00:00Z',
  ended_at: '2026-09-03T11:00:00Z',
  language: 'en',
  twitch_stream_id: 'twitch-7',
  recording_path: '/recordings/7.mp4',
  episode_number: 7,
}

describe('StreamCard expansion', () => {
  it('does not expand when its row or body is clicked', async () => {
    const wrapper = mount(StreamCard, { props: { stream } })

    await wrapper.get('.stream-compact').trigger('click')
    await wrapper.get('.stream-card-content').trigger('click')

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

    await button.trigger('click')
    expect(button.attributes('aria-expanded')).toBe('false')
    expect(button.attributes('aria-controls')).toBe(controlsBefore)
    expect(wrapper.find('.stream-expanded').exists()).toBe(false)
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

describe('StreamCard compact summary', () => {
  it.each([
    {
      name: 'in progress with no recording',
      stream: { ended_at: null, recording_path: null, is_live: false, is_recording: false },
      status: 'In progress',
      availability: 'Recording unavailable',
    },
    {
      name: 'in progress with a recording path',
      stream: { ended_at: null, recording_path: '/stale.mp4', is_live: false, is_recording: false },
      status: 'In progress',
      availability: 'Recording available',
    },
    {
      name: 'ended with a recording',
      stream: { ended_at: '2026-09-03T11:00:00Z', recording_path: '/recordings/7.mp4', is_live: true, is_recording: true },
      status: 'Ended',
      availability: 'Recording available',
    },
    {
      name: 'ended without a recording',
      stream: { ended_at: '2026-09-03T11:00:00Z', recording_path: '   ', is_live: true, is_recording: true },
      status: 'Ended',
      availability: 'Recording unavailable',
    },
  ])('derives $name only from ended_at and recording_path', ({ stream: overrides, status, availability }) => {
    const contradictoryStream = { ...stream, ...overrides } as Stream
    const wrapper = mount(StreamCard, { props: { stream: contradictoryStream } })

    expect(wrapper.get('.stream-lifecycle').text()).toBe(status)
    expect(wrapper.get('.stream-recording-availability').text()).toBe(availability)
  })

  it('keeps title, start, duration, category, and status visible while collapsed', () => {
    const wrapper = mount(StreamCard, { props: { stream } })

    expect(wrapper.get('.stream-title').text()).toBe(stream.title)
    expect(wrapper.get('time.stream-start').attributes('datetime')).toBe(stream.started_at)
    expect(wrapper.get('.stream-duration').text()).toBe('1h 0m')
    expect(wrapper.get('.category-badge').text()).toContain(stream.category_name)
    expect(wrapper.get('.stream-lifecycle').text()).toBe('Ended')
    expect(wrapper.get('.stream-recording-availability').text()).toBe('Recording available')
    expect(wrapper.find('.stream-expanded').exists()).toBe(false)
  })

  it('uses two-line title clipping and the required compact row heights', () => {
    expect(streamCardSource).toMatch(/\.stream-compact\s*\{[\s\S]*?min-height:\s*72px;/)
    expect(streamCardSource).toMatch(/\.stream-title\s*\{[\s\S]*?-webkit-line-clamp:\s*2;/)
    expect(streamCardSource).toMatch(/@include m\.respond-below\('sm'\)[\s\S]*?\.stream-compact\s*\{[\s\S]*?min-height:\s*80px;/)
    expect(streamCardSource).toMatch(/\.expanded-actions \.action-item\s*\{[\s\S]*?min-height:\s*44px;/)
  })
})
