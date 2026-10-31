import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CleanupPolicyEditor from '@/components/CleanupPolicyEditor.vue'
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import { useRecordingStore } from '@/stores/recordings'
import { CleanupPolicyType, type CleanupPolicy } from '@/types/recording'

vi.mock('@/composables/useFilenamePresets', () => ({
  useFilenamePresets: () => ({ presets: [], isLoading: false, error: null })
}))

const original = { type: CleanupPolicyType.COUNT, threshold: 10, preserve_favorites: true, preserve_categories: [] }
const draft: CleanupPolicy = { type: CleanupPolicyType.AGE, threshold: 37, preserve_favorites: false, preserve_categories: ['Synthetic'] }
const settings = { enabled: false, filename_template: '{streamer}', default_quality: 'best', use_chapters: true, cleanup_policy: original }
const channel = { streamer_id: 7, username: 'synthetic', enabled: false, twitch_auth_priority: 0, use_global_cleanup_policy: false, cleanup_policy: original }
let persisted = structuredClone(settings)
let persistedChannel = structuredClone(channel)
let failure: 'http' | 'network' | 'readback' | null = null
let writes: { url: string; body: Record<string, unknown> }[] = []
const wrappers: ReturnType<typeof mount>[] = []

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(useRecordingStore(), 'bindRealtime').mockReturnValue(() => {})
  persisted = structuredClone(settings)
  persistedChannel = structuredClone(channel)
  writes = []
  failure = null
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === 'POST') {
      const body = JSON.parse(String(init.body))
      writes.push({ url, body })
      if (failure === 'network') throw new TypeError('Failed to fetch')
      if (failure === 'http') return new Response('{}', { status: 500 })
      if (url === '/api/recording/settings') persisted = body
      else if (url === '/api/recording/streamers/7/cleanup-policy') persistedChannel = { ...persistedChannel, ...body }
      else throw new Error(`Unexpected write ${url}`)
      return Response.json(persisted)
    }
    if (url === '/api/recording/settings') return Response.json(persisted)
    if (url === '/api/recording/streamers') return failure === 'readback' ? new Response('{}', { status: 500 }) : Response.json([persistedChannel])
    if (url === '/api/categories') return Response.json({ categories: [{ id: 1, name: 'Synthetic' }] })
    if (url === '/api/recording/storage/7') return Response.json({ totalSize: 0, recordingCount: 0, oldestRecording: '', newestRecording: '' })
    throw new Error(`Unexpected request ${url}`)
  }))
})

afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function editor(isGlobal: boolean, inPanel = false) {
  const store = useRecordingStore()
  store.settings = structuredClone(settings)
  store.streamerSettings = [structuredClone(channel)]
  const wrapper = inPanel
    ? mount(RecordingSettingsPanel, { attachTo: document.body, props: { settings: store.settings, streamerSettings: store.streamerSettings, activeRecordings: [], section: isGlobal ? 'storage' : 'recording' } })
    : mount(CleanupPolicyEditor, { props: { title: 'Synthetic policy', isGlobal, streamerId: isGlobal ? undefined : 7 } })
  wrappers.push(wrapper)
  if (inPanel && !isGlobal) {
    await wrapper.get('button[title="Configure cleanup policy for this streamer"]').trigger('click')
  }
  await flushPromises()
  const form = wrapper.getComponent(CleanupPolicyEditor)
  await form.get('select').setValue('age')
  await form.get('input[type="number"]').setValue('37')
  const checks = form.findAll('input[type="checkbox"]')
  await checks[isGlobal ? 0 : 1]!.setValue(false)
  await form.get('select[multiple]').setValue(['Synthetic'])
  return { wrapper, form, store }
}

function expectDraft(form: Awaited<ReturnType<typeof editor>>['form']) {
  expect((form.get('select').element as HTMLSelectElement).value).toBe('age')
  expect((form.get('input[type="number"]').element as HTMLInputElement).value).toBe('37')
  expect((form.findAll('input[type="checkbox"]').at(-1)!.element as HTMLInputElement).checked).toBe(false)
  expect(Array.from((form.get('select[multiple]').element as HTMLSelectElement).selectedOptions, option => option.value)).toEqual(['Synthetic'])
}

describe.each([true, false])('cleanup persistence isGlobal=%s', isGlobal => {
  it.each(['http', 'network'] as const)('keeps draft/dialog after %s failure, retries and reloads persisted policy', async mode => {
    const { wrapper, form, store } = await editor(isGlobal, true)
    failure = mode
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(form.emitted('saved')).toBeUndefined()
    expect(form.find('.message.success').exists()).toBe(false)
    expect(form.get('.message.error').text()).toMatch(/saving cleanup policy/i)
    expect(form.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.findComponent(CleanupPolicyEditor).exists()).toBe(true)
    expectDraft(form)
    expect(store.settings?.cleanup_policy).toEqual(original)
    expect(store.streamerSettings[0]?.cleanup_policy).toEqual(original)
    expect(persisted.cleanup_policy).toEqual(original)
    expect(persistedChannel.cleanup_policy).toEqual(original)
    failure = null
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(form.emitted('saved')).toEqual([[draft]])
    expect(writes).toHaveLength(2)
    expect(writes[1]?.body).toEqual(writes[0]?.body)
    expect(isGlobal ? persisted.cleanup_policy : persistedChannel.cleanup_policy).toEqual(draft)
    if (!isGlobal) expect(wrapper.findComponent(CleanupPolicyEditor).exists()).toBe(false)
    await store.fetchSettings()
    await store.fetchStreamerSettings()
    expect(isGlobal ? store.settings?.cleanup_policy : store.streamerSettings[0]?.cleanup_policy).toEqual(draft)
  })

  it.each(['false', 'reject'] as const)('does not emit success when the action returns %s', async mode => {
    const action = vi.spyOn(useRecordingStore(), isGlobal ? 'updateCleanupPolicy' : 'updateStreamerCleanupPolicy')
    if (mode === 'false') action.mockResolvedValue(false)
    else action.mockRejectedValue(new Error('Synthetic rejection'))
    const { form } = await editor(isGlobal)
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(form.emitted('saved')).toBeUndefined()
    expect(form.find('.message.success').exists()).toBe(false)
    expect(form.get('.message.error').text()).toMatch(/saving cleanup policy/i)
    expectDraft(form)
  })
})

it('does not claim channel success or replace state if the post-save readback fails', async () => {
  const { form, store } = await editor(false)
  failure = 'readback'
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(form.emitted('saved')).toBeUndefined()
  expect(form.find('.message.error').exists()).toBe(true)
  expect(store.streamerSettings[0]?.cleanup_policy).toEqual(original)
  expectDraft(form)
})

it('does not claim success without a channel target', async () => {
  const wrapper = mount(CleanupPolicyEditor, { props: { title: 'Missing target', isGlobal: false } })
  wrappers.push(wrapper)
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('saved')).toBeUndefined()
  expect(wrapper.find('.message.error').exists()).toBe(true)
  expect(writes).toHaveLength(0)
})
