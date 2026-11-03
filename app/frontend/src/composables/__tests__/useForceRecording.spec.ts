import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useForceRecording } from '../useForceRecording'

const mocks = vi.hoisted(() => ({ checkLiveStatus: vi.fn(), forceStartRecording: vi.fn() }))
vi.mock('@/services/api', () => ({ streamersApi: mocks, recordingApi: mocks }))
beforeEach(() => vi.resetAllMocks())

describe('force recording shared facade', () => {
  it('handles the unwrapped backend success and invokes its completion callback', async () => {
    mocks.checkLiveStatus.mockResolvedValue({ is_live: true })
    mocks.forceStartRecording.mockResolvedValue({ status: 'success' })
    const completed = vi.fn()
    const recording = useForceRecording()
    await expect(recording.forceStartRecording(42, completed)).resolves.toEqual({ success: true })
    expect(completed).toHaveBeenCalledExactlyOnceWith(42)
    expect(recording.forceRecordingStreamerId.value).toBeNull()
  })
  it('does not emit completion when the recording request fails', async () => {
    mocks.forceStartRecording.mockRejectedValue(new Error('offline'))
    const completed = vi.fn()
    expect((await useForceRecording().forceStartRecording(42, completed)).success).toBe(false)
    expect(completed).not.toHaveBeenCalled()
  })
})
