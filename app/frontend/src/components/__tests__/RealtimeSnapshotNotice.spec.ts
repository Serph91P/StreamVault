import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const state = reactive({ snapshotRevision: 0 })
vi.mock('@/stores/realtime', () => ({ useRealtimeStore: () => state }))
import RealtimeSnapshotNotice from '../RealtimeSnapshotNotice.vue'

describe('page-owned last-known realtime projections', () => {
  it('marks previously mounted page data stale after lost history, without claiming notifications are complete', async () => {
    const view = mount(RealtimeSnapshotNotice)
    expect(view.find('[role="status"]').exists()).toBe(false)
    state.snapshotRevision++
    await nextTick()
    expect(view.get('[role="status"]').text()).toContain('Last-known status')
    expect(view.text()).toContain('Reopen this view')
    expect(view.text()).toContain('Notification history may be incomplete')
    view.unmount()
    const freshView = mount(RealtimeSnapshotNotice)
    expect(freshView.find('[role="status"]').exists()).toBe(false)
    freshView.unmount()
  })
})
