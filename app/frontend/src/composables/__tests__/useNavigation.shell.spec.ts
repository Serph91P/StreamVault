import { describe, expect, it } from 'vitest'
import { navigationTabs, utilityTabs } from '@/composables/useNavigation'

 describe('shell navigation contract', () => {
  it('offers exactly three consistent everyday destinations', () => {
    expect(navigationTabs.map((tab) => [tab.route, tab.label])).toEqual([
      ['/streamers', 'Kanäle'],
      ['/videos', 'Aufnahmen'],
      ['/activity', 'Aktivität'],
    ])
  })

  it('keeps settings and system in a separate utility group', () => {
    expect(utilityTabs.map((tab) => tab.route)).toEqual(['/settings', '/system'])
  })
})
