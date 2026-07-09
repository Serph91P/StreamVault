import type {
  ActiveRecording,
  CleanupPolicy,
  RecordingSettings,
  StreamerRecordingSettings
} from '@/types/recording'

export interface CleanupResult {
  status: string
  message: string
  deleted_count: number
  deleted_paths: string[]
}

export interface StreamerStorageUsage {
  totalSize: number
  recordingCount: number
  oldestRecording: string
  newestRecording: string
}

export interface CategoryOption {
  id: number
  name: string
}

async function readJsonResponse<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) {
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function fetchRecordingSettings(): Promise<RecordingSettings> {
  const response = await fetch('/api/recording/settings', {
    credentials: 'include'
  })
  return readJsonResponse<RecordingSettings>(response, 'Failed to load settings')
}

export async function saveRecordingSettings(settings: RecordingSettings): Promise<RecordingSettings> {
  const response = await fetch('/api/recording/settings', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      enabled: settings.enabled,
      filename_template: settings.filename_template,
      filename_preset: settings.filename_preset,
      default_quality: settings.default_quality,
      use_chapters: settings.use_chapters,
      use_category_as_chapter_title: settings.use_category_as_chapter_title,
      cleanup_policy: settings.cleanup_policy
    })
  })
  return readJsonResponse<RecordingSettings>(response, 'Failed to update settings')
}

export async function fetchStreamerRecordingSettings(): Promise<StreamerRecordingSettings[]> {
  const response = await fetch('/api/recording/streamers', {
    credentials: 'include'
  })
  if (!response.ok) {
    const errorText = await response.text()
    console.error('Error response:', errorText)
    throw new Error(`HTTP error! Status: ${response.status}`)
  }
  return response.json() as Promise<StreamerRecordingSettings[]>
}

export async function saveStreamerRecordingSettings(
  streamerId: number,
  settings: Partial<StreamerRecordingSettings>
): Promise<StreamerRecordingSettings> {
  const response = await fetch(`/api/recording/streamers/${streamerId}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      streamer_id: streamerId,
      ...settings
    })
  })

  if (!response.ok) {
    const data = await response.json()
    throw new Error(data.detail || `HTTP error! Status: ${response.status}`)
  }

  return response.json() as Promise<StreamerRecordingSettings>
}

export async function fetchActiveRecordings(): Promise<ActiveRecording[]> {
  const response = await fetch('/api/recording/active', {
    credentials: 'include'
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch active recordings: ${response.status}`)
  }

  const data = await response.json()
  if (!Array.isArray(data)) {
    console.error('Invalid active recordings response:', data)
    return []
  }

  return data as ActiveRecording[]
}

export async function stopStreamerRecording(streamerId: number): Promise<void> {
  const response = await fetch(`/api/recording/stop/${streamerId}`, {
    method: 'POST',
    credentials: 'include'
  })

  if (!response.ok) {
    throw new Error(`HTTP error! Status: ${response.status}`)
  }
}

export async function cleanupRecordings(streamerId: number): Promise<CleanupResult> {
  const response = await fetch(`/api/recording/cleanup/${streamerId}`, {
    method: 'POST',
    credentials: 'include'
  })
  return readJsonResponse<CleanupResult>(
    response,
    `Failed to cleanup old recordings: ${response.statusText}`
  )
}

export async function saveStreamerCleanupPolicy(
  streamerId: number,
  policy: CleanupPolicy,
  useGlobal: boolean
): Promise<void> {
  const response = await fetch(`/api/recording/streamers/${streamerId}/cleanup-policy`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      cleanup_policy: useGlobal ? null : policy,
      use_global_cleanup_policy: useGlobal
    })
  })

  if (!response.ok) {
    throw new Error('Failed to update streamer cleanup policy')
  }
}

export async function runCleanup(
  streamerId: number,
  customPolicy?: CleanupPolicy
): Promise<CleanupResult> {
  const url = customPolicy
    ? `/api/recording/cleanup/${streamerId}/custom`
    : `/api/recording/cleanup/${streamerId}`

  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json'
    },
    body: customPolicy ? JSON.stringify(customPolicy) : undefined
  })

  return readJsonResponse<CleanupResult>(response, `Failed to run cleanup: ${response.statusText}`)
}

export async function fetchStreamerStorageUsage(streamerId: number): Promise<StreamerStorageUsage> {
  const response = await fetch(`/api/recording/storage/${streamerId}`, {
    credentials: 'include'
  })

  return readJsonResponse<StreamerStorageUsage>(
    response,
    `Failed to get storage usage: ${response.statusText}`
  )
}

export async function fetchAvailableCategories(): Promise<CategoryOption[]> {
  const response = await fetch('/api/categories', {
    credentials: 'include'
  })
  if (!response.ok) {
    throw new Error('Failed to fetch categories')
  }
  const data = await response.json()
  return data.categories.map((category: CategoryOption) => ({
    id: category.id,
    name: category.name
  }))
}
