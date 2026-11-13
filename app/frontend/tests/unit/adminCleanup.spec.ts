import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminPanel from '@/components/admin/AdminPanel.vue'

const endpoint = '/api/admin/maintenance/cleanup-temp'
const candidate = { path: 'old.tmp', device: '1', inode: '2', size: '12', mtime_ns: '1700000000000000001' }

afterEach(() => vi.unstubAllGlobals())

describe('admin temporary cleanup confirmation', () => {
  it.each(['confirmed', 'cancelled', 'empty', 'error'] as const)('%s uses preview before any destructive request', async (mode) => {
    const confirm = vi.fn((_message: string) => mode === 'confirmed')
    vi.stubGlobal('confirm', confirm)
    const requests: RequestInit[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) !== endpoint) return Response.json(null)
      requests.push(init ?? {})
      if (mode === 'error') return Response.json({ detail: 'synthetic preview error' }, { status: 500 })
      return Response.json({
        dry_run: requests.length === 1,
        files_removed: requests.length === 1 ? 0 : 1,
        space_freed_mb: 0,
        errors: [],
        candidates: mode === 'empty' ? [] : [candidate],
      })
    }))
    const wrapper = mount(AdminPanel, { global: { stubs: {
      WebSocketMonitor: true, BackgroundQueueMonitor: true,
      BackgroundQueueAdmin: true, PostProcessingManagement: true,
    } } })
    try {
      await flushPromises()
      const button = wrapper.findAll('button').find(button => button.text().includes('Cleanup Temp Files'))
      expect(button).toBeDefined()
      await button!.trigger('click')
      await flushPromises()
      expect(JSON.parse(String(requests[0]?.body ?? '{}'))).toEqual({ dry_run: true })
      expect(requests).toHaveLength(mode === 'confirmed' ? 2 : 1)
      expect(confirm).toHaveBeenCalledTimes(mode === 'confirmed' || mode === 'cancelled' ? 1 : 0)
      if (mode === 'confirmed' || mode === 'cancelled') {
        const prompt = String(confirm.mock.calls[0]?.[0])
        for (const value of ['1', 'unowned', '24', candidate.path]) expect(prompt).toContain(value)
      }
      if (mode === 'confirmed') {
        expect(JSON.parse(String(requests[1]?.body))).toEqual({ dry_run: false, confirmed: true, candidates: [candidate] })
        expect(wrapper.text()).toContain('Files removed: 1')
      } else if (mode === 'error') {
        expect(wrapper.text()).toContain('synthetic preview error')
      } else {
        expect(wrapper.text()).toContain('Cleanup Preview')
        expect(wrapper.text()).toContain('Files removed: 0')
      }
    } finally {
      wrapper.unmount()
    }
  })
})
