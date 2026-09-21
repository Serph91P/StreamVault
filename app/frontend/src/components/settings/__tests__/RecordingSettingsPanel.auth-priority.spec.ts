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


describe('RecordingSettingsPanel Twitch auth priority', () => {
  it('shows and emits a bounded priority for every streamer', async () => {
    const wrapper = mount(RecordingSettingsPanel, {
      global: { plugins: [createPinia()] },
      props: {
        settings: null,
        activeRecordings: [],
        streamerSettings: [
          {
            streamer_id: 7,
            username: 'priority-channel',
            enabled: true,
            twitch_auth_priority: 0
          }
        ]
      }
    })

    const input = wrapper.get('[aria-label="Twitch authentication priority for priority-channel"]')
    await input.setValue('100')
    await input.trigger('change')

    expect(wrapper.emitted('updateStreamer')).toContainEqual([
      7,
      { twitch_auth_priority: 100 }
    ])
    expect(wrapper.text()).toContain('Auth priority')
    expect(wrapper.text()).toContain('-1000 to 1000')
    wrapper.unmount()
  })

  it('shows effective mode, pending handoff reason, and partial recording warning', () => {
    const wrapper = mount(RecordingSettingsPanel, {
      global: { plugins: [createPinia()] },
      props: {
        settings: null,
        streamerSettings: [],
        activeRecordings: [
          {
            streamer_id: 7,
            streamer_name: 'priority-channel',
            started_at: '2026-09-21T12:00:00Z',
            file_path: '/recordings/priority.ts',
            status: 'recording',
            duration: 30,
            twitch_auth_priority: 100,
            effective_auth_mode: 'anonymous',
            pending_handoff: true,
            handoff_reason: 'awaiting_higher_priority_handoff',
            partial_recording_warning: true
          }
        ]
      }
    })

    expect(wrapper.text()).toContain('Twitch mode: anonymous')
    expect(wrapper.text()).toContain('Auth priority: 100')
    expect(wrapper.text()).toContain(
      'Auth handoff pending: awaiting_higher_priority_handoff'
    )
    expect(wrapper.text()).toContain(
      'Recording may contain a short segment-boundary gap after the auth handoff.'
    )
    wrapper.unmount()
  })
})
