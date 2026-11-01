import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import { FILENAME_PRESETS, type RecordingSettings } from '@/types/recording'

vi.mock('@/composables/useRecordingSettings', () => ({
  useRecordingSettings: () => ({ isLoading: false, error: null }),
}))
vi.mock('@/composables/useFilenamePresets', () => ({
  useFilenamePresets: () => ({ presets: FILENAME_PRESETS, isLoading: false, error: null }),
}))

const settings: RecordingSettings = {
  enabled: true, default_quality: 'best', filename_preset: 'default',
  filename_template: '{streamer}/{title}', use_chapters: true,
  use_category_as_chapter_title: false, supported_codecs: 'h264,h265', prefer_higher_quality: true,
}
function panel() {
  return mount(RecordingSettingsPanel, {
    attachTo: document.body,
    global: { plugins: [createPinia()] },
    props: {
      settings: { ...settings }, activeRecordings: [],
      streamerSettings: [{ streamer_id: 7, username: 'channel-7', enabled: true, quality: '', custom_filename: '', twitch_auth_priority: -25 }],
    },
  })
}
function field(wrapper: ReturnType<typeof panel>, name: string) {
  const label = wrapper.findAll('label').find(node => node.text() === name)
  expect(label, name).toBeDefined()
  const id = label!.attributes('for')
  expect(id, name).toBeTruthy()
  return wrapper.get(`[id="${id}"]`)
}

describe('RecordingSettingsPanel accessible controls', () => {
  it('keeps native label targets unique across simultaneous panel instances', () => {
    const host = mount({
      components: { RecordingSettingsPanel },
      setup: () => ({ settings, streamers: [{ streamer_id: 7, username: 'channel-7', enabled: true, twitch_auth_priority: -25 }] }),
      template: '<RecordingSettingsPanel v-for="index in 2" :key="index" :settings="settings" :streamer-settings="streamers" :active-recordings="[]" />',
    }, { attachTo: document.body, global: { plugins: [createPinia()] } })
    try {
      for (const wrapper of host.findAllComponents(RecordingSettingsPanel)) {
        for (const name of ['Default Quality:', 'Filename Template:', 'Custom Filename Template:', 'Supported Codecs:', 'Record channel-7', 'Quality for channel-7', 'Custom Filename for channel-7']) {
          const input = field(wrapper, name)
          expect(document.querySelectorAll(`[id="${input.attributes('id')}"]`)).toHaveLength(1)
        }
      }
    } finally { host.unmount() }
  })

  it('emits the same complete global values after labelled codec, preset and filename edits', async () => {
    const wrapper = panel()
    try {
      await field(wrapper, 'Default Quality:').setValue('720p')
      await field(wrapper, 'Supported Codecs:').setValue('av1')
      await field(wrapper, 'Filename Template:').setValue('plex')
      expect((field(wrapper, 'Custom Filename Template:').element as HTMLInputElement).value).toBe(FILENAME_PRESETS.find(preset => preset.value === 'plex')!.description)
      await field(wrapper, 'Custom Filename Template:').setValue('saved/{title}')
      await wrapper.get('.form-actions button').trigger('click')
      expect(wrapper.emitted('update')).toEqual([[{
        ...settings, default_quality: '720p', supported_codecs: 'av1', filename_preset: 'plex', filename_template: 'saved/{title}',
      }]])
    } finally { wrapper.unmount() }
  })

  it('preserves exact streamer update emits without legacy priority or unrelated values', async () => {
    const wrapper = panel()
    try {
      await field(wrapper, 'Record channel-7').setValue(false)
      await field(wrapper, 'Quality for channel-7').setValue('480p')
      await field(wrapper, 'Custom Filename for channel-7').setValue('channel/{title}')
      expect(wrapper.emitted('updateStreamer')).toEqual([
        [7, { enabled: false }], [7, { quality: '480p' }], [7, { custom_filename: 'channel/{title}' }],
      ])
    } finally { wrapper.unmount() }
  })
})
