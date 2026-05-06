/**
 * Single source of truth for per-streamer settings fields.
 *
 * Mirrors the backend models:
 *   - app/models.py :: StreamerRecordingSettings  (recording.*)
 *   - app/models.py :: NotificationSettings       (notifications.*)
 *
 * Used by AddStreamerForm and the StreamerDetail settings modal so both
 * surfaces stay in sync. Adding a field here automatically renders it
 * (no per-page hardcoded markup, no phantom fields).
 */

export type FieldType = 'text' | 'select' | 'checkbox' | 'number'

export interface SelectOption {
  value: string
  label: string
}

export interface FieldSchema {
  /** Backend field name */
  key: string
  /** UI label */
  label: string
  /** Optional help text under the input */
  help?: string
  type: FieldType
  /** Default value used by AddStreamerForm */
  default: unknown
  /** Options for select fields */
  options?: SelectOption[]
  /** When set, field is only rendered if `dependsOn(state)` returns true */
  dependsOn?: (state: Record<string, unknown>) => boolean
  /** Optional placeholder for text inputs */
  placeholder?: string
}

export interface FieldGroup {
  /** Stable id (also used as event-namespace prefix) */
  id: string
  /** Section title in the UI */
  title: string
  /**
   * Backend payload key this group serializes into. The form builds:
   *   { [group.payloadKey]: { [field.key]: value, ... } }
   */
  payloadKey: 'recording' | 'notifications' | 'root'
  fields: FieldSchema[]
}

const QUALITY_OPTIONS: SelectOption[] = [
  { value: 'best', label: 'Best' },
  { value: '1080p60', label: '1080p60' },
  { value: '1080p', label: '1080p' },
  { value: '720p60', label: '720p60' },
  { value: '720p', label: '720p' },
  { value: '480p', label: '480p' },
  { value: '360p', label: '360p' },
  { value: '160p', label: '160p' },
  { value: 'audio_only', label: 'Audio Only' },
]

const RECORDING_QUALITY_OPTIONS: SelectOption[] = [
  { value: '', label: 'Use global default' },
  ...QUALITY_OPTIONS.filter(o => o.value !== 'audio_only'),
]

export const STREAMER_FIELD_GROUPS: FieldGroup[] = [
  {
    id: 'quality',
    title: 'Stream Quality',
    payloadKey: 'root',
    fields: [
      {
        key: 'quality',
        label: 'Quality',
        type: 'select',
        default: 'best',
        options: QUALITY_OPTIONS,
      },
    ],
  },
  {
    id: 'notifications',
    title: 'Notification Settings',
    payloadKey: 'notifications',
    fields: [
      {
        key: 'notify_online',
        label: 'Online',
        help: 'Notify when stream starts',
        type: 'checkbox',
        default: true,
      },
      {
        key: 'notify_offline',
        label: 'Offline',
        help: 'Notify when stream ends',
        type: 'checkbox',
        default: true,
      },
      {
        key: 'notify_update',
        label: 'Updates',
        help: 'Notify on title/category changes',
        type: 'checkbox',
        default: true,
      },
      {
        key: 'notify_favorite_category',
        label: 'Favorites',
        help: 'Notify when streaming favorite games',
        type: 'checkbox',
        default: true,
      },
    ],
  },
  {
    id: 'recording',
    title: 'Recording Settings',
    payloadKey: 'recording',
    fields: [
      {
        key: 'enabled',
        label: 'Enable Recording',
        help: 'Automatically record streams',
        type: 'checkbox',
        default: true,
      },
      {
        key: 'quality',
        label: 'Recording Quality',
        type: 'select',
        default: '',
        options: RECORDING_QUALITY_OPTIONS,
        dependsOn: (state) => Boolean((state.recording as Record<string, unknown>)?.enabled),
      },
      {
        key: 'custom_filename',
        label: 'Custom Filename Template',
        help: 'Leave empty to use global template',
        type: 'text',
        default: '',
        placeholder: 'Use global template',
        dependsOn: (state) => Boolean((state.recording as Record<string, unknown>)?.enabled),
      },
    ],
  },
]

/**
 * Build the initial reactive state object from the schema defaults.
 * Returns shape: { quality, notifications: {...}, recording: {...} }
 */
export function buildDefaultState(): Record<string, unknown> {
  const state: Record<string, unknown> = {
    quality: 'best',
    notifications: {} as Record<string, unknown>,
    recording: {} as Record<string, unknown>,
  }
  for (const group of STREAMER_FIELD_GROUPS) {
    if (group.payloadKey === 'root') {
      for (const f of group.fields) {
        state[f.key] = f.default
      }
    } else {
      const bucket = state[group.payloadKey] as Record<string, unknown>
      for (const f of group.fields) {
        bucket[f.key] = f.default
      }
    }
  }
  return state
}
