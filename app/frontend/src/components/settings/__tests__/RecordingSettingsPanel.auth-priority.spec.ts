import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/composables/useRecordingSettings', () => ({
  useRecordingSettings: () => ({ isLoading: false, error: null })
}))
vi.mock('@/composables/useFilenamePresets', () => ({
  useFilenamePresets: () => ({ presets: [], isLoading: false, error: null })
}))

import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import type { ActiveRecording } from '@/types/recording'

function mountPanel(activeRecordings: ActiveRecording[] = []) {
  return mount(RecordingSettingsPanel, {
    global: { plugins: [createPinia()] },
    props: {
      context: 'channel',
      settings: null,
      activeRecordings,
      streamerSettings: [{
        streamer_id: 7,
        username: 'priority-channel',
        enabled: true,
        quality: '',
        twitch_auth_priority: -25
      }]
    }
  })
}

describe('RecordingSettingsPanel dormant Twitch auth priority compatibility', () => {
  it('does not render or emit the compatibility-only priority field', async () => {
    const wrapper = mountPanel()

    const checkbox = wrapper.get('[aria-label="Aufnahme für priority-channel"]')
    await checkbox.setValue(false)
    await checkbox.trigger('change')

    expect(wrapper.emitted('updateStreamer')).toContainEqual([7, { enabled: false }])
    expect(wrapper.find('[aria-label*="authentication priority"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Auth priority')
    expect(wrapper.emitted('updateStreamer')).not.toContainEqual([
      7,
      expect.objectContaining({ twitch_auth_priority: expect.anything() })
    ])
    wrapper.unmount()
  })

  it('keeps stored priority values out of unrelated streamer mutations', async () => {
    const wrapper = mountPanel()

    const quality = wrapper.get('select.form-control-sm')
    await quality.setValue('720p')
    await quality.trigger('change')

    expect(wrapper.emitted('updateStreamer')).toContainEqual([7, { quality: '720p' }])
    expect(JSON.stringify(wrapper.emitted('updateStreamer'))).not.toContain('twitch_auth_priority')
    wrapper.unmount()
  })

  it('shows mode and safety warnings without priority-specific UI', () => {
    const wrapper = mountPanel([{
      id: 11,
      stream_id: 12,
      streamer_id: 7,
      streamer_name: 'priority-channel',
      title: 'Synthetic recording',
      started_at: '2026-09-21T12:00:00Z',
      file_path: '/recordings/priority.ts',
      status: 'recording',
      duration: 30,
      twitch_auth_priority: 100,
      effective_auth_mode: 'anonymous',
      pending_handoff: true,
      handoff_reason: 'awaiting_higher_priority_handoff',
      partial_recording_warning: true
    }])

    expect(wrapper.text()).toContain('Twitch-Zugang: anonymous')
    expect(wrapper.text()).not.toContain('Auth priority')
    expect(wrapper.text()).not.toContain('higher_priority')
    expect(wrapper.text()).toContain('Waiting for authenticated recording capacity.')
    expect(wrapper.text()).toContain(
      'A short segment-boundary gap may follow this auth handoff.'
    )
    wrapper.unmount()
  })

  it('does not turn a dormant legacy marker into a handoff or gap warning', () => {
    const wrapper = mountPanel([{
      id: 21,
      stream_id: 22,
      streamer_id: 7,
      streamer_name: 'priority-channel',
      title: 'Synthetic recording',
      started_at: '2026-09-21T12:00:00Z',
      file_path: '/recordings/priority.ts',
      status: 'recording',
      duration: 30,
      effective_auth_mode: 'authenticated',
      pending_handoff: false,
      handoff_reason: 'awaiting_higher_priority_handoff',
      partial_recording_warning: true
    }])

    expect(wrapper.text()).not.toContain('Waiting for authenticated recording capacity.')
    expect(wrapper.text()).not.toContain('segment-boundary gap')
    wrapper.unmount()
  })
})