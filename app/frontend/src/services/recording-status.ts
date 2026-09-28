export interface RecordingStatusSource {
  status?: string
  twitch_auth_priority?: number
  effective_auth_mode?: 'authenticated' | 'anonymous' | 'unknown'
  pending_handoff?: boolean
  handoff_reason?: string
  partial_recording_warning?: boolean
}

export interface RecordingStatusSummary {
  label: string
  priority?: number
  handoff?: string
  partialWarning?: string
}

/**
 * Maps the recording backend contract to copy that can be shared by recording
 * consumers. It deliberately preserves persisted priorities (including
 * negatives) and never turns capacity handoff into an offline streamer state.
 */
export function toRecordingStatusSummary(recording: RecordingStatusSource): RecordingStatusSummary {
  const isPending = recording.pending_handoff || recording.status === 'pending'
  const authMode = recording.effective_auth_mode ?? 'unknown'

  const label = authMode === 'unknown'
    ? 'Recording; Twitch mode unknown'
    : authMode === 'authenticated'
      ? 'Authenticated Twitch recording'
      : isPending
        ? 'Waiting for recording capacity'
        : 'Anonymous Twitch recording'

  return {
    label,
    priority: recording.twitch_auth_priority,
    handoff: recording.handoff_reason || (isPending
      ? 'Waiting for authenticated recording capacity.'
      : undefined),
    partialWarning: recording.partial_recording_warning
      ? 'A short segment-boundary gap may follow this auth handoff.'
      : undefined
  }
}
