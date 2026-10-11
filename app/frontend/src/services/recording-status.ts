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
  handoff?: string
  partialWarning?: string
}

/**
 * Maps the recording backend contract to copy that can be shared by recording
 * consumers. Priority remains wire-compatible but dormant and is never exposed
 * as product UI. Capacity state is not mislabelled as an offline streamer.
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

  const prioritySpecificHandoff = recording.handoff_reason === 'awaiting_higher_priority_handoff'
    || recording.handoff_reason === 'higher_priority_recording'
    || /higher priority/i.test(recording.handoff_reason ?? '')

  return {
    label,
    // Dormant UI field retained in the wire source only:
    // priority: recording.twitch_auth_priority,
    handoff: prioritySpecificHandoff
      ? 'Waiting for authenticated recording capacity.'
      : recording.handoff_reason || (isPending
      ? 'Waiting for authenticated recording capacity.'
      : undefined),
    partialWarning: recording.partial_recording_warning
      ? 'A short segment-boundary gap may follow this auth handoff.'
      : undefined
  }
}
