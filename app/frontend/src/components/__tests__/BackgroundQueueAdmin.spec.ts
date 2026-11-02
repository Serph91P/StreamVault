import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BackgroundQueueAdmin from '../admin/BackgroundQueueAdmin.vue'

const queueStatus = {
  total_external_tasks: 2, total_active_tasks: 1, stuck_recordings: 1,
  continuous_orphaned: 1, unknown_tasks: 1, total_issues: 3,
  stuck_recording_tasks: ['recording-1'], orphaned_recovery_tasks: ['recovery-1'],
  unknown_task_names: ['unknown-1'],
}
const cleanupResult = { success: true, message: 'Cleaned', total_issues_fixed: 3 }
const response = (body: unknown) => new Response(JSON.stringify(body), {
  headers: { 'Content-Type': 'application/json' },
})
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

const wrappers: VueWrapper[] = []
function visit() {
  const wrapper = mount(BackgroundQueueAdmin)
  wrappers.push(wrapper)
  return wrapper
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => response(queueStatus)))
  vi.spyOn(console, 'debug').mockImplementation(() => undefined)
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('BackgroundQueueAdmin lifecycle', () => {
  it('loads immediately and keeps only the current visit polling', async () => {
    for (let visitNumber = 1; visitNumber <= 3; visitNumber++) {
      const wrapper = visit()
      await flushPromises()
      expect(wrapper.text()).toContain('External Tasks:2')
      expect(fetch).toHaveBeenCalledTimes(visitNumber * 2 - 1)
      await vi.advanceTimersByTimeAsync(30_000)
      expect(fetch).toHaveBeenCalledTimes(visitNumber * 2)
      wrapper.unmount()
      await vi.advanceTimersByTimeAsync(60_000)
      expect(fetch).toHaveBeenCalledTimes(visitNumber * 2)
      expect(vi.getTimerCount()).toBe(0)
    }
  })

  it('does not overlap a slow status request and resumes after an error', async () => {
    const pending = deferred<Response>()
    vi.mocked(fetch).mockReturnValueOnce(pending.promise)
    const wrapper = visit()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetch).toHaveBeenCalledTimes(1)
    pending.reject(new Error('offline'))
    await flushPromises()
    expect(wrapper.text()).toContain('Error loading status: offline')
    await vi.advanceTimersByTimeAsync(30_000)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('External Tasks:2')
  })

  it.each(['resolve', 'reject', 'body'] as const)('ignores late status %s after unmount and aborts transport', async outcome => {
    const pending = deferred<Response>()
    const body = deferred<typeof queueStatus>()
    vi.mocked(fetch).mockReturnValueOnce(pending.promise)
    const wrapper = visit()
    if (outcome === 'body') {
      pending.resolve({ ok: true, json: () => body.promise } as Response)
      await flushPromises()
    }
    const state = wrapper.vm as unknown as { status: unknown; lastResult: unknown; loading: boolean }
    const before = { status: state.status, lastResult: state.lastResult, loading: state.loading }
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal
    wrapper.unmount()
    expect(signal?.aborted).toBe(true)
    if (outcome === 'reject') pending.reject(new Error('late failure'))
    else if (outcome === 'body') body.resolve(queueStatus)
    else pending.resolve(response(queueStatus))
    await flushPromises()
    expect({ status: state.status, lastResult: state.lastResult, loading: state.loading }).toEqual(before)
    expect(console.error).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['all', 'stuck-recordings', 'orphaned-recovery', 'task-names'])('cancels the delayed refresh after %s cleanup', async endpoint => {
    const wrapper = visit()
    await flushPromises()
    vi.mocked(fetch).mockResolvedValueOnce(response(cleanupResult))
    const buttonIndex = ['all', 'stuck-recordings', 'orphaned-recovery', 'task-names'].indexOf(endpoint) + 1
    await wrapper.findAll('button')[buttonIndex].trigger('click')
    await flushPromises()
    expect(fetch).toHaveBeenLastCalledWith(`/api/admin/background-queue/cleanup/${endpoint}`, expect.objectContaining({ method: 'POST', credentials: 'include' }))
    expect(wrapper.text()).toContain('Cleaned')
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['resolve', 'reject'] as const)('ignores cleanup %s after unmount without scheduling more work', async outcome => {
    const wrapper = visit()
    await flushPromises()
    const pending = deferred<Response>()
    vi.mocked(fetch).mockReturnValueOnce(pending.promise)
    await wrapper.findAll('button')[1].trigger('click')
    const state = wrapper.vm as unknown as { lastResult: unknown; loading: boolean }
    const before = { lastResult: state.lastResult, loading: state.loading }
    const signal = vi.mocked(fetch).mock.calls[1][1]?.signal
    wrapper.unmount()
    expect(signal?.aborted).toBe(true)
    if (outcome === 'resolve') pending.resolve(response(cleanupResult))
    else pending.reject(new Error('late cleanup failure'))
    await flushPromises()
    expect({ lastResult: state.lastResult, loading: state.loading }).toEqual(before)
    expect(console.error).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('still refreshes after a successful cleanup while mounted', async () => {
    const wrapper = visit()
    await flushPromises()
    vi.mocked(fetch).mockResolvedValueOnce(response(cleanupResult))
    await wrapper.findAll('button')[1].trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetch).toHaveBeenCalledTimes(3)
    expect(wrapper.text()).toContain('Cleaned')
    expect(wrapper.findAll('button')[0].attributes('disabled')).toBeUndefined()
  })
})
