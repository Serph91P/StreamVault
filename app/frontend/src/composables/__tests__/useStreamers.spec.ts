import { afterEach, describe, expect, it, vi } from 'vitest'

const { getAll, deleteStreamer } = vi.hoisted(() => ({
  getAll: vi.fn(),
  deleteStreamer: vi.fn()
}))

vi.mock('@/services/api', () => ({
  streamersApi: {
    getAll,
    delete: deleteStreamer
  }
}))

import { useStreamers } from '../useStreamers'

const streamer = {
  id: 'streamer-1',
  twitch_id: 'twitch-1',
  username: 'streamer',
  is_live: false,
  is_recording: false,
  recording_enabled: true
}

describe('useStreamers', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('loads streamers through the shared facade and clears loading after success', async () => {
    getAll.mockResolvedValue({ streamers: [streamer] })
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { streamers, isLoading, fetchStreamers } = useStreamers()

    const loading = fetchStreamers()
    expect(isLoading.value).toBe(true)

    await loading

    expect(getAll).toHaveBeenCalledOnce()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(streamers.value).toEqual([streamer])
    expect(isLoading.value).toBe(false)
  })

  it('preserves streamers and clears loading after a facade failure', async () => {
    getAll.mockRejectedValue(new Error('unavailable'))
    const { streamers, isLoading, fetchStreamers } = useStreamers()
    streamers.value = [streamer]

    await fetchStreamers()

    expect(streamers.value).toEqual([streamer])
    expect(isLoading.value).toBe(false)
  })

  it('removes a streamer only after the shared delete facade succeeds', async () => {
    deleteStreamer.mockResolvedValue({ success: true })
    const { streamers, deleteStreamer: removeStreamer } = useStreamers()
    streamers.value = [streamer]

    await expect(removeStreamer(streamer.id)).resolves.toBe(true)

    expect(deleteStreamer).toHaveBeenCalledWith(streamer.id)
    expect(streamers.value).toEqual([])
  })

  it('keeps a streamer when the shared delete facade rejects', async () => {
    const { streamers, deleteStreamer: removeStreamer } = useStreamers()
    streamers.value = [streamer]

    deleteStreamer.mockRejectedValue(new Error('unavailable'))
    await expect(removeStreamer(streamer.id)).resolves.toBe(false)
    expect(streamers.value).toEqual([streamer])
  })
})
