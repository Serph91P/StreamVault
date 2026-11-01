import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import CleanupPolicyEditor from '@/components/CleanupPolicyEditor.vue'

vi.mock('@/composables/useRecordingSettings', () => ({
  useRecordingSettings: () => ({
    settings: ref({ cleanup_policy: { type: 'count', threshold: 10, preserve_favorites: true, preserve_categories: [] } }),
    getAvailableCategories: async () => [{ id: 1, name: 'Games' }],
  }),
}))

describe('CleanupPolicyEditor native labels', () => {
  it('associates all three visible labels uniquely across simultaneous editors', async () => {
    const host = mount({
      components: { CleanupPolicyEditor },
      template: '<CleanupPolicyEditor v-for="index in 2" :key="index" :is-global="true" title="Global policy" />',
    }, { attachTo: document.body })
    try {
      await flushPromises()
      for (const editor of host.findAllComponents(CleanupPolicyEditor)) {
        for (const text of ['Cleanup Policy:', 'Number of recordings to keep:', 'Preserve Categories:']) {
          const label = editor.findAll('label').find(node => node.text() === text)!
          const id = label.attributes('for')
          expect(id, text).toBeTruthy()
          const field = editor.get(`[id="${id}"]`)
          expect(document.querySelectorAll(`[id="${id}"]`)).toHaveLength(1)
          expect((field.element as HTMLInputElement).labels?.[0]).toBe(label.element)
        }
      }
    } finally { host.unmount() }
  })
})
