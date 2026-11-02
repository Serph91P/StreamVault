import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import RecordingSettingsPanel from '../RecordingSettingsPanel.vue'
import NotificationSettingsPanel from '../NotificationSettingsPanel.vue'
import StreamerSettingsFields from '@/components/streamers/StreamerSettingsFields.vue'
import { buildDefaultState } from '@/schemas/streamerSettings.schema'

vi.mock('@/composables/useRecordingSettings', () => ({
  useRecordingSettings: () => ({ isLoading: false, error: null })
}))
vi.mock('@/composables/useFilenamePresets', () => ({
  useFilenamePresets: () => ({ presets: [], isLoading: false, error: null })
}))
const channel = { streamer_id: 7, username: 'test-channel', enabled: true, quality: '', twitch_auth_priority: 0 }
const recording = { id: 1, stream_id: 2, streamer_id: 7, streamer_name: 'test-channel', title: 'Test', started_at: '2026-10-01T10:00:00Z', file_path: '/recordings/test.ts', status: 'recording', duration: 30 }
const notification = { streamer_id: 7, username: 'test-channel', notify_online: true, notify_offline: true, notify_update: true, notify_favorite_category: true }
const notificationSettings = { notification_url: '', notifications_enabled: false, apprise_docs_url: '', notify_online_global: true, notify_offline_global: true, notify_update_global: true }
const global = { plugins: [createPinia()], stubs: { CleanupPolicyEditor: true, BaseModal: { template: '<div><slot /></div>' } } }

describe('settings context boundaries', () => {
  it('uses associated native Base fields and keeps owner pending/results inline', async () => {
    const wrapper = mount(RecordingSettingsPanel, { global, props: { settings: null, streamerSettings: [], activeRecordings: [], saveState: 'pending' } })
    const quality = wrapper.get('select')
    expect(wrapper.find(`label[for="${quality.attributes('id')}"]`).text()).toContain('Standardqualität')
    expect((wrapper.get('.form-actions button').element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.get('[data-state="pending"]').attributes('role')).toBe('status')
    await wrapper.setProps({ saveState: 'failure', saveMessage: 'Nicht gespeichert. Entwurf bleibt erhalten.' })
    expect(wrapper.get('[role="alert"]').text()).toContain('Entwurf bleibt erhalten')
    expect((wrapper.get('.form-actions button').element as HTMLButtonElement).disabled).toBe(false)
    wrapper.unmount()
  })
  it('avoids duplicate overrides beside the schema editor while preserving channel operations', async () => {
    const wrapper = mount(RecordingSettingsPanel, { global, props: { context: 'channel', showOverrides: false, settings: null, streamerSettings: [channel], activeRecordings: [recording] } })
    expect(wrapper.find('tbody input').exists()).toBe(false)
    expect(wrapper.find('tbody select').exists()).toBe(false)
    expect(wrapper.find('.active-recordings button').exists()).toBe(true)
    await wrapper.get('.actions-group button[title]').trigger('click')
    expect(wrapper.findComponent({ name: 'CleanupPolicyEditor' }).props('streamerId')).toBe(7)
    const notifications = mount(NotificationSettingsPanel, { global, props: { context: 'channel', showOverrides: false, settings: notificationSettings, streamerSettings: [notification] } })
    expect(notifications.find('tbody input').exists()).toBe(false)
    await notifications.get('.btn-group button').trigger('click')
    expect(notifications.emitted('update-streamer-settings')).toEqual([[7, { notify_online: true, notify_offline: true, notify_update: true, notify_favorite_category: true }]])
  })
  it('lets the cleanup editor own inheritance without hiding any other schema field', () => {
    const wrapper = mount(StreamerSettingsFields, { props: { modelValue: buildDefaultState(), excludeFields: ['recording.use_global_cleanup_policy'] } })
    expect(wrapper.text()).not.toContain('Use Global Cleanup Policy')
    expect(wrapper.find('#field-recording-supported_codecs').exists()).toBe(true)
    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(5)
  })
  it('keeps global recording controls but no channels or active recording controls', () => {
    const wrapper = mount(RecordingSettingsPanel, { global, props: { settings: null, streamerSettings: [channel], activeRecordings: [recording] } })
    expect(wrapper.find('select').exists()).toBe(true)
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('test-channel')
    expect(wrapper.find('.active-recordings').exists()).toBe(false)
  })
  it('keeps global notification controls without a per-channel table or bulk actions', () => {
    const wrapper = mount(NotificationSettingsPanel, { global, props: { settings: notificationSettings, streamerSettings: [notification] } })
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.find('.table-controls').exists()).toBe(false)
  })
  it('keeps overrides and stop in channel context, without cross-channel bulk actions', async () => {
    const wrapper = mount(RecordingSettingsPanel, { global, props: { context: 'channel', settings: null, streamerSettings: [channel], activeRecordings: [recording] } })
    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.find('.table-controls').exists()).toBe(false)
    expect(wrapper.find('.form-actions').exists()).toBe(false)
    await wrapper.get('.active-recordings button').trigger('click')
    expect(wrapper.emitted('stopRecording')).toEqual([[7]])
    expect(wrapper.findAllComponents({ name: 'CleanupPolicyEditor' })).toHaveLength(0)
    await wrapper.get('.actions-group button[title]').trigger('click')
    expect(wrapper.findComponent({ name: 'CleanupPolicyEditor' }).props('streamerId')).toBe(7)
  })
  it('moves recording bulk and active recordings to management without overrides', async () => {
    const wrapper = mount(RecordingSettingsPanel, { global, props: { context: 'manage', settings: null, streamerSettings: [channel], activeRecordings: [recording] } })
    expect(wrapper.find('table').exists()).toBe(false)
    await wrapper.get('.table-controls button').trigger('click')
    expect(wrapper.emitted('updateStreamer')).toEqual([[7, { enabled: true }]])
    expect(wrapper.find('.active-recordings').exists()).toBe(true)
  })
  it('keeps all four channel notification toggles and moves bulk-only controls to management', async () => {
    const wrapper = mount(NotificationSettingsPanel, { global, props: { context: 'manage', settings: notificationSettings, streamerSettings: [notification] } })
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.find('.input-with-tooltip').exists()).toBe(false)
    await wrapper.get('.table-controls button').trigger('click')
    expect(wrapper.emitted('update-streamer-settings')).toEqual([[7, { notify_online: true, notify_offline: true, notify_update: true }]])
    await wrapper.setProps({ context: 'channel' })
    expect(wrapper.find('.table-controls').exists()).toBe(false)
    expect(wrapper.findAll('tbody input[type="checkbox"]')).toHaveLength(4)
  })
})
