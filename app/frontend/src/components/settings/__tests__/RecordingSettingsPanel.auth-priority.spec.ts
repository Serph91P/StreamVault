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

function mountPanel(activeRecordings: any[] = []) {
  return mount(RecordingSettingsPanel, {
    global: { plugins: [createPinia()] },
    props: {
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

    const checkbox = wrapper.get('[aria-label="Record priority-channel"]')
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
    }])

    expect(wrapper.text()).toContain('Twitch mode: anonymous')
    expect(wrapper.text()).not.toContain('Auth priority')
    expect(wrapper.text()).not.toContain('higher_priority')
    expect(wrapper.text()).toContain('Twitch authentication transition pending')
    expect(wrapper.text()).toContain(
      'Recording may contain a short segment-boundary gap after the auth handoff.'
    )
    wrapper.unmount()
  })
})