import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import NotificationSettingsPanel from '../NotificationSettingsPanel.vue'

const settings = {
  notification_url: 'https://synthetic.invalid/original',
  notifications_enabled: false,
  apprise_docs_url: 'https://github.com/caronc/apprise/wiki#notification-services',
  notify_online_global: true,
  notify_offline_global: false,
  notify_update_global: true,
  notify_favorite_category_global: false,
  notify_recording_started: false,
  notify_recording_failed: true,
  notify_recording_completed: false,
}

describe('NotificationSettingsPanel', () => {
  it('preserves blur/debounced validation and emits the complete edited preferences only on save', async () => {
    vi.useFakeTimers()
    const wrapper = mount(NotificationSettingsPanel, { props: { settings, streamerSettings: [] } })
    try {
      const input = wrapper.get('input[type="text"]')
      const save = wrapper.get('.form-actions button')
      await input.setValue('invalid-url')
      await input.trigger('blur')
      expect(input.attributes('aria-invalid')).toBe('true')
      expect(save.attributes('disabled')).toBeDefined()
      expect(wrapper.emitted('update-settings')).toBeUndefined()

      await input.setValue('ntfy://synthetic.invalid/topic, https://synthetic.invalid/notifications')
      await vi.runAllTimersAsync()
      expect(input.attributes('aria-invalid')).toBeUndefined()
      await wrapper.get('.form-check input').setValue(true)
      expect(wrapper.emitted('update-settings')).toBeUndefined()
      await save.trigger('click')
      expect(wrapper.emitted('update-settings')).toEqual([[{
        notification_url: 'ntfy://synthetic.invalid/topic, https://synthetic.invalid/notifications',
        notifications_enabled: true,
        notify_online_global: true,
        notify_offline_global: false,
        notify_update_global: true,
        notify_favorite_category_global: false,
        notify_recording_started: false,
        notify_recording_failed: true,
        notify_recording_completed: false,
      }]])
    } finally {
      wrapper.unmount()
      vi.useRealTimers()
    }
  })
})
