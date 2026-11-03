import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import RecordingSettingsPanel from '../RecordingSettingsPanel.vue'
import { saveRecordingSettings } from '@/services/recording'
import { useRecordingStore } from '@/stores/recordings'
import { CleanupPolicyType, FILENAME_PRESETS, type RecordingSettings } from '@/types/recording'

vi.mock('@/composables/useRecordingSettings', () => ({
  useRecordingSettings: () => ({ isLoading: false, error: null }),
}))
vi.mock('@/composables/useFilenamePresets', () => ({
  useFilenamePresets: () => ({ presets: FILENAME_PRESETS, isLoading: false, error: null }),
}))
afterEach(() => vi.unstubAllGlobals())

const unchanged = {
  enabled: false, output_directory: '/synthetic/recordings', default_quality: '720p',
  filename_template: '{streamer}/{title}', filename_preset: 'custom',
  use_chapters: false, use_category_as_chapter_title: true,
  cleanup_policy: { type: CleanupPolicyType.COUNT, threshold: 5, preserve_favorites: false, preserve_categories: ['synthetic'] },
}

describe('codec-only saves preserve authoritative retention', () => {
  // Removing either panel hydration/emission or service serialization must fail these cases.
  it.each([7, 0].flatMap(limit => [false, true].map(delayed => ({ limit, delayed }))))(
    'preserves limit $limit with delayed hydration=$delayed through panel → store → service',
    async ({ limit, delayed }) => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const loaded = { ...unchanged, supported_codecs: 'h264', max_streams_per_streamer: limit }
      const store = useRecordingStore()
      store.settings = loaded
      let posted: Record<string, unknown> | undefined
      vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
        posted = JSON.parse(String(init?.body))
        return { ok: true, json: async () => ({ ...loaded, supported_codecs: 'h265' }) }
      }))
      const wrapper = mount(RecordingSettingsPanel, {
        global: { plugins: [pinia] },
        props: { settings: delayed ? null : loaded, streamerSettings: [], activeRecordings: [], onUpdate: store.updateSettings },
      })
      try {
        if (delayed) await wrapper.setProps({ settings: loaded })
        const codecLabel = wrapper.findAll('label').find(label => label.text() === 'Erlaubte Codecs:')!
        await wrapper.get(`select[id="${codecLabel.attributes('for')}"]`).setValue('h265')
        await wrapper.get('.form-actions button').trigger('click')
        await flushPromises()
        expect(wrapper.emitted('update')?.[0]?.[0]).toMatchObject({ max_streams_per_streamer: limit })
        expect(posted).toEqual({ ...unchanged, supported_codecs: 'h265', max_streams_per_streamer: limit })
        expect(store.settings).toMatchObject({ ...loaded, supported_codecs: 'h265' })
      } finally { wrapper.unmount() }
    },
  )

  it.each([7, 0])('recovers missing legacy caller limit from GET (%s), not a guessed default', async limit => {
    const requests: { method: string; body?: Record<string, unknown> }[] = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
      requests.push({ method: init?.method || 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined })
      return { ok: true, json: async () => ({ ...unchanged, max_streams_per_streamer: limit }) }
    }))
    await saveRecordingSettings({ ...unchanged, supported_codecs: 'h265' })
    expect(requests).toEqual([
      { method: 'GET', body: undefined },
      { method: 'POST', body: { ...unchanged, supported_codecs: 'h265', max_streams_per_streamer: limit } },
    ])
  })

  it.each([undefined, null])('does not POST if the authoritative limit is unavailable (%s)', async limit => {
    const methods: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
      methods.push(init?.method || 'GET')
      return { ok: true, json: async () => ({ ...unchanged, max_streams_per_streamer: limit }) }
    }))
    await expect(saveRecordingSettings(unchanged as RecordingSettings)).rejects.toThrow('retention limit')
    expect(methods).toEqual(['GET'])
  })
})
