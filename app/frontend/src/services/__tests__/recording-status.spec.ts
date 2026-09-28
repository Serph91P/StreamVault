import { afterEach, describe, expect, it, vi } from 'vitest'

import { recordingApi } from '@/services/api-real'
import { toRecordingStatusSummary } from '@/services/recording-status'
import routeResponse from '../../../tests/fixtures/recording-active-status-contract.json'

describe('toRecordingStatusSummary', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('consumes the verified /api/recording/active fixture through the real facade', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(routeResponse), {
      status: 200,
      headers: { 'content-type': 'application/json' }
    }))
    vi.stubGlobal('fetch', fetchMock)

    const recordings = await recordingApi.getActiveRecordings()

    expect(fetchMock).toHaveBeenCalledWith('/api/recording/active', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(toRecordingStatusSummary(recordings[0])).toEqual({
      label: 'Authenticated Twitch recording',
      priority: -25,
      handoff: 'awaiting_higher_priority_handoff',
      partialWarning: 'A short segment-boundary gap may follow this auth handoff.'
    })
    expect(toRecordingStatusSummary(recordings[1])).toEqual({
      label: 'Anonymous Twitch recording',
      priority: 17,
      handoff: 'live_playback_owner_not_preemptible',
      partialWarning: undefined
    })
  })

  it('keeps a negative persisted priority and explains an authenticated handoff', () => {
    expect(toRecordingStatusSummary({
      status: 'recording',
      twitch_auth_priority: -25,
      effective_auth_mode: 'authenticated',
      pending_handoff: true,
      handoff_reason: 'Higher priority recording is waiting for capacity',
      partial_recording_warning: true
    })).toEqual({
      label: 'Authenticated Twitch recording',
      priority: -25,
      handoff: 'Higher priority recording is waiting for capacity',
      partialWarning: 'A short segment-boundary gap may follow this auth handoff.'
    })
  })

  it('does not describe a pending slot conflict as an offline stream', () => {
    expect(toRecordingStatusSummary({
      status: 'pending',
      effective_auth_mode: 'anonymous',
      pending_handoff: true
    })).toMatchObject({
      label: 'Waiting for recording capacity',
      handoff: 'Waiting for authenticated recording capacity.'
    })
  })

  it('keeps an active anonymous recording visible while explaining its blocked handoff', () => {
    expect(toRecordingStatusSummary({
      status: 'recording',
      twitch_auth_priority: 17,
      effective_auth_mode: 'anonymous',
      pending_handoff: false,
      handoff_reason: 'live_playback_owner_not_preemptible'
    })).toEqual({
      label: 'Anonymous Twitch recording',
      priority: 17,
      handoff: 'live_playback_owner_not_preemptible',
      partialWarning: undefined
    })
  })

  it('keeps unknown auth mode explicit when the backend does not report one', () => {
    expect(toRecordingStatusSummary({ status: 'recording' })).toMatchObject({
      label: 'Recording; Twitch mode unknown',
      priority: undefined
    })
  })
})
