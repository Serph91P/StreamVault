import { describe, expect, it } from 'vitest'
import { navigationTabs } from '@/composables/useNavigation'

describe('shell navigation contract', () => {
  it('prioritizes channels and separates activity, global settings and system tools', () => {
    expect(navigationTabs.map((tab) => [tab.route, tab.label])).toEqual([
      ['/streamers', 'Kanäle'],
      ['/videos', 'Aufzeichnungen'],
      ['/activity', 'Aktivität'],
      ['/settings', 'Einstellungen'],
      ['/system', 'System'],
    ])
  })
})
