import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/components/settings/TwitchConnectionPanel.vue', () => ({
  default: { template: '<label>Draft <input v-model="draft" data-testid="draft" /></label>', data: () => ({ draft: '' }) }
}))
const { inertPanel } = vi.hoisted(() => ({
  inertPanel: () => ({ default: { template: '<p data-testid="inert">Inert</p>' } })
}))
vi.mock('@/components/settings/NotificationSettingsPanel.vue', inertPanel)
vi.mock('@/components/settings/RecordingSettingsPanel.vue', inertPanel)
vi.mock('@/components/settings/FavoritesSettingsPanel.vue', inertPanel)
vi.mock('@/components/settings/PWAPanel.vue', inertPanel)
vi.mock('@/components/settings/ApiKeysPanel.vue', inertPanel)
vi.mock('@/components/settings/ProxySettingsPanel.vue', inertPanel)

import SettingsPanelHost from '@/components/settings/SettingsPanelHost.vue'

describe('SettingsPanelHost', () => {
  it('keeps dirty panel state while switching sections', async () => {
    const wrapper = mount(SettingsPanelHost, {
      props: { section: 'twitch', panelProps: {}, panelListeners: {} }
    })

    await wrapper.get('[data-testid="draft"]').setValue('unsaved')
    await wrapper.setProps({ section: 'notifications' })
    expect(wrapper.get('[data-testid="inert"]').text()).toBe('Inert')

    await wrapper.setProps({ section: 'twitch' })
    await nextTick()
    expect((wrapper.get('[data-testid="draft"]').element as HTMLInputElement).value).toBe('unsaved')
  })
})
