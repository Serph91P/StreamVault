import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/components/settings/TwitchConnectionPanel.vue', () => ({
  default: { template: '<label>Draft <input v-model="draft" data-testid="draft" /></label>', data: () => ({ draft: '' }) }
}))
const { inertPanel } = vi.hoisted(() => ({
  inertPanel: () => ({ default: { template: '<p data-testid="inert">Inert</p><p data-testid="fragment-tail">Fragment tail</p>' } })
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

  it('hides every fragment root of inactive panels without discarding their drafts', async () => {
    const warnings: string[] = []
    const wrapper = mount(SettingsPanelHost, {
      attachTo: document.body,
      props: { section: 'twitch', panelProps: {}, panelListeners: {} },
      global: { config: { warnHandler: message => warnings.push(message) } }
    })
    await wrapper.get('[data-testid="draft"]').setValue('unsaved fragment regression')
    for (const section of ['notifications', 'recording', 'storage', 'favorites', 'pwa', 'api-keys', 'proxy']) {
      await wrapper.setProps({ section })
      expect(wrapper.findAll('[data-testid="inert"]').filter(root => root.isVisible()), `${section}: ${wrapper.html()}`).toHaveLength(1)
      expect(wrapper.findAll('[data-testid="fragment-tail"]').filter(root => root.isVisible()), section).toHaveLength(1)
      expect(wrapper.get('[data-testid="draft"]').isVisible()).toBe(false)
    }
    await wrapper.setProps({ section: 'about' })
    expect(wrapper.findAll('[data-testid="inert"]').every(root => !root.isVisible())).toBe(true)
    expect(wrapper.findAll('[data-testid="fragment-tail"]').every(root => !root.isVisible())).toBe(true)
    await wrapper.setProps({ section: 'notifications' })
    expect(wrapper.findAll('[data-testid="inert"]').filter(root => root.isVisible())).toHaveLength(1)
    await wrapper.setProps({ section: 'twitch' })
    expect(wrapper.findAll('[data-testid="inert"]').every(root => !root.isVisible())).toBe(true)
    expect(wrapper.findAll('[data-testid="fragment-tail"]').every(root => !root.isVisible())).toBe(true)
    expect((wrapper.get('[data-testid="draft"]').element as HTMLInputElement).value).toBe('unsaved fragment regression')
    expect(warnings.filter(message => message.includes('Runtime directive used on component with non-element root node'))).toEqual([])
    wrapper.unmount()
  })
})
