import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { describe, expect, it } from 'vitest'
import AddStreamerView from '../AddStreamerView.vue'

describe('Twitch callback destination', () => {
  it('opens the import route with the callback query intact', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/add-streamer', name: 'add-streamer', component: AddStreamerView },
      { path: '/add-streamer/import', name: 'add-streamer-import', component: AddStreamerView },
    ] })
    await router.push('/add-streamer?auth_success=true')
    const wrapper = mount(AddStreamerView, { global: { plugins: [router], directives: { ripple: {} }, stubs: { BaseModal: true, AddStreamerForm: true, TwitchImportForm: true } } })
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('add-streamer-import')
    expect(router.currentRoute.value.query).toEqual({ auth_success: 'true' })
    wrapper.unmount()
  })
})
