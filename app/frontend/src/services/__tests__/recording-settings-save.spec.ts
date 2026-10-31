import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { saveRecordingSettings } from '@/services/recording'
import { useRecordingStore } from '@/stores/recordings'

const settings = { enabled: true, default_quality: '720p', filename_template: '{streamer}', use_chapters: true, supported_codecs: 'av1' }
afterEach(() => vi.unstubAllGlobals())
describe('recording settings persistence', () => {
  it('sends the selected global codecs to the recording API', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => settings })
    vi.stubGlobal('fetch', fetchMock)
    await saveRecordingSettings(settings)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ supported_codecs: 'av1' })
  })
  it('preserves the server-owned output directory when saving visible recording options', async () => {
    setActivePinia(createPinia())
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => settings })
    vi.stubGlobal('fetch', fetchMock)
    const store = useRecordingStore()
    store.settings = { ...settings, output_directory: '/synthetic/custom-recordings' }
    await store.updateSettings(settings)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toHaveProperty('output_directory', '/synthetic/custom-recordings')
  })
  it('rejects a failed global save so the view cannot report success', async () => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    const store = useRecordingStore()
    await expect(store.updateSettings(settings)).rejects.toThrow('Failed to update settings')
    expect(store.error).toBe('Failed to update settings')
  })
})
