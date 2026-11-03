import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  fetchSettings: vi.fn(), fetchStreamerSettings: vi.fn(), fetchActiveRecordings: vi.fn(),
  updateStreamerSettings: vi.fn(), stopRecording: vi.fn(),
  fetchNotifications: vi.fn(), getNotifications: vi.fn(), updateNotifications: vi.fn(),
  success: vi.fn(), error: vi.fn()
}))
vi.mock('@/composables/useRecordingSettings', () => ({ useRecordingSettings: () => ({
  settings: ref(null), streamerSettings: ref([{ streamer_id: 7, username: 'one' }, { streamer_id: 8, username: 'two' }]),
  activeRecordings: ref([{ streamer_id: 7 }, { streamer_id: 8 }]), error: ref(null),
  fetchSettings: api.fetchSettings, fetchStreamerSettings: api.fetchStreamerSettings,
  fetchActiveRecordings: api.fetchActiveRecordings, updateStreamerSettings: api.updateStreamerSettings,
  stopRecording: api.stopRecording
}) }))
vi.mock('@/composables/useNotificationSettings', () => ({ useNotificationSettings: () => ({
  settings: ref({}), streamerSettings: ref([{ streamer_id: 7 }, { streamer_id: 8 }]),
  fetchSettings: api.fetchNotifications, getStreamerSettings: api.getNotifications,
  updateStreamerSettings: api.updateNotifications
}) }))
vi.mock('@/composables/useToast', () => ({ useToast: () => ({ success: api.success, error: api.error }) }))
import ChannelSettingsPanel from '../ChannelSettingsPanel.vue'

const global = { stubs: { RecordingSettingsPanel: true, NotificationSettingsPanel: true, RouterLink: true } }
beforeEach(() => { vi.clearAllMocks() })
describe('ChannelSettingsPanel integration', () => {
  it('loads actual settings and scopes all child data to the current route channel', async () => {
    const wrapper = mount(ChannelSettingsPanel, { global, props: { streamerId: 7 } })
    await flushPromises()
    expect(api.fetchSettings).toHaveBeenCalledOnce()
    expect(api.fetchStreamerSettings).toHaveBeenCalledOnce()
    expect(api.fetchActiveRecordings).toHaveBeenCalledOnce()
    expect(api.getNotifications).toHaveBeenCalledOnce()
    const recording = wrapper.getComponent({ name: 'RecordingSettingsPanel' })
    expect(recording.props('streamerSettings')).toEqual([{ streamer_id: 7, username: 'one' }])
    expect(recording.props('activeRecordings')).toEqual([{ streamer_id: 7 }])
    expect(recording.props('context')).toBe('channel')
    expect(wrapper.getComponent({ name: 'NotificationSettingsPanel' }).props('streamerSettings')).toEqual([{ streamer_id: 7 }])
    await wrapper.setProps({ streamerId: 8 })
    expect(recording.props('streamerSettings')).toEqual([{ streamer_id: 8, username: 'two' }])
  })
  it('keeps management bulk targets intact and links each channel to its settings', async () => {
    const wrapper = mount(ChannelSettingsPanel, { global })
    await flushPromises()
    expect(wrapper.getComponent({ name: 'RecordingSettingsPanel' }).props('context')).toBe('manage')
    expect(wrapper.getComponent({ name: 'RecordingSettingsPanel' }).props('streamerSettings')).toHaveLength(2)
    expect(wrapper.findAllComponents({ name: 'RouterLink' }).map(link => link.props('to'))).toEqual([
      { path: '/streamers/7', query: { tab: 'settings' } }, { path: '/streamers/8', query: { tab: 'settings' } }
    ])
  })
  it('dispatches existing recording and notification mutations, and does not claim a failed stop succeeded', async () => {
    const wrapper = mount(ChannelSettingsPanel, { global, props: { streamerId: 7 } })
    await flushPromises()
    wrapper.getComponent({ name: 'RecordingSettingsPanel' }).vm.$emit('updateStreamer', 7, { enabled: false })
    wrapper.getComponent({ name: 'NotificationSettingsPanel' }).vm.$emit('update-streamer-settings', 7, { notify_online: false })
    await flushPromises()
    expect(api.updateStreamerSettings).toHaveBeenCalledWith(7, { enabled: false })
    expect(api.updateNotifications).toHaveBeenCalledWith(7, { notify_online: false })
    expect(wrapper.emitted('recordingUpdated')).toEqual([[{ enabled: false }]])
    expect(wrapper.emitted('notificationsUpdated')).toEqual([[{ notify_online: false }]])
    api.stopRecording.mockResolvedValueOnce(false)
    api.success.mockClear()
    wrapper.getComponent({ name: 'RecordingSettingsPanel' }).vm.$emit('stopRecording', 7)
    await flushPromises()
    expect(api.stopRecording).toHaveBeenCalledWith(7)
    expect(api.success).not.toHaveBeenCalled()
    expect(api.error).toHaveBeenCalled()
  })
})
