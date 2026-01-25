<template>
  <div class="streams-container">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <div class="spinner"></div>
      <p>Loading streams...</p>
    </div>
    
    <!-- Empty State -->
    <div v-else-if="streams.length === 0" class="empty-state">
      <!-- Header for empty state -->
      <div v-if="!hideHeader" class="page-header" style="margin-bottom: 20px;">
        <div class="header-left">
          <button @click="handleBack" class="back-button">
            <i class="fas fa-arrow-left"></i>
            Streamers
          </button>
          <div class="header-info">
            <h1>{{ streamerName || 'Recent Streams' }}</h1>
            <p class="stream-count">No streams yet</p>
          </div>
        </div>
        
        <div class="header-actions">
          <button 
            @click="forceStartRecordingWithLocalUpdate(Number(streamerId))" 
            class="btn btn-success"
            :disabled="forceRecordingStreamerId === Number(streamerId)"
            title="Force Start Recording - Checks if streamer is currently live and starts recording automatically"
            aria-label="Force start recording for this streamer - validates live status via API and begins recording if online"
            :aria-describedby="forceRecordingStreamerId === Number(streamerId) ? 'force-recording-status' : undefined"
          >
            <span v-if="forceRecordingStreamerId === Number(streamerId)" id="force-recording-status">
              <i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Checking & Starting...
            </span>
            <span v-else>
              <i class="fas fa-record-vinyl" aria-hidden="true"></i> Force Record Streamer
            </span>
          </button>
        </div>
      </div>
      
      <div class="empty-icon">🎬</div>
      <h3>No Streams Found</h3>
      <p>This streamer hasn't streamed yet or all streams have been deleted.</p>
    </div>
    
    <!-- Streams Content -->
    <div v-else class="streams-content">
      <!-- Header (conditional) -->
      <div v-if="!hideHeader" class="page-header">
        <div class="header-left">
          <button @click="handleBack" class="back-button">
            <i class="fas fa-arrow-left"></i>
            Streamers
          </button>
          <div class="header-info">
            <h1>{{ streamerName || 'Recent Streams' }}</h1>
            <p class="stream-count">{{ streams.length }} {{ streams.length === 1 ? 'stream' : 'streams' }}</p>
          </div>
        </div>
        
        <div class="header-actions">
          <button 
            @click="forceStartRecordingWithLocalUpdate(Number(streamerId))" 
            class="btn btn-success"
            :disabled="forceRecordingStreamerId === Number(streamerId)"
            title="Force Start Recording - Checks if streamer is currently live and starts recording automatically"
            aria-label="Force start recording for this streamer - validates live status via API and begins recording if online"
            :aria-describedby="forceRecordingStreamerId === Number(streamerId) ? 'force-recording-status' : undefined"
          >
            <span v-if="forceRecordingStreamerId === Number(streamerId)" id="force-recording-status">
              <i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Checking & Starting...
            </span>
            <span v-else>
              <i class="fas fa-record-vinyl" aria-hidden="true"></i> Force Record Streamer
            </span>
          </button>
          
          <button 
            v-if="streams.length > 1"
            @click="confirmDeleteAllStreams" 
            class="btn btn-danger"
            :disabled="deletingAllStreams"
            aria-label="Delete all streams for this streamer permanently"
            :aria-describedby="deletingAllStreams ? 'delete-all-status' : undefined"
          >
            <span v-if="deletingAllStreams" id="delete-all-status">
              🗑️ Deleting...
            </span>
            <span v-else>
              🗑️ Delete All ({{ streams.length }})
            </span>
          </button>
        </div>
      </div>
      
      <!-- Stream Grid -->
      <div class="stream-grid">
        <div 
          v-for="stream in sortedStreams" 
          :key="stream.id"
          class="stream-card"
          :class="{ 
            'live': !stream.ended_at,
            'recording': isStreamBeingRecorded(stream)
          }"
        >
          <!-- Stream Info -->
          <div class="stream-info">
            <div class="stream-header">
              <div class="title-and-badges">
                <h3 class="stream-title">{{ stream.title || 'Untitled Stream' }}</h3>
                <div class="stream-meta-badges">
                  <span v-if="!stream.ended_at" class="status-badge live">
                    <i class="fas fa-circle"></i> LIVE
                  </span>
                  <span v-else class="status-badge ended">
                    <i class="fas fa-stop-circle"></i> ENDED
                  </span>
                  
                  <span 
                    v-if="!stream.ended_at && isStreamBeingRecorded(stream)" 
                    class="status-badge recording"
                  >
                    <i class="fas fa-record-vinyl recording-pulse"></i> RECORDING
                  </span>
                  <span 
                    v-else-if="!stream.ended_at" 
                    class="status-badge not-recording"
                  >
                    <i class="fas fa-circle-o"></i> NOT RECORDING
                  </span>
                  
                  <span 
                    v-if="stream.ended_at && hasRecording(stream)" 
                    class="status-badge has-recording"
                  >
                    <i class="fas fa-video"></i> VIDEO
                  </span>
                </div>
              </div>
              
              <div class="stream-meta">
                <span class="stream-date">{{ formatDate(stream.started_at) }}</span>
                <span v-if="stream.category_name" class="stream-category">
                  <i class="fas fa-tag"></i> {{ stream.category_name }}
                </span>
              </div>
            </div>
            
            <!-- Stream Actions -->
            <div class="stream-actions">
              <!-- Recording Actions (Primary Actions) -->
              <div class="recording-actions">
                <!-- Watch Video Button (for ended streams with recording) -->
                <button 
                  v-if="stream.ended_at && hasRecording(stream)"
                  @click="watchVideo(stream)" 
                  class="btn btn-primary action-btn"
                  title="Watch Video"
                  :aria-label="`Watch recorded video of ${stream.title || 'Untitled Stream'}`"
                >
                  <i class="fas fa-play" aria-hidden="true"></i> Watch Video
                </button>
                
                <!-- Stop Recording Button (for active recordings) -->
                <button 
                  v-if="!stream.ended_at && isStreamBeingRecorded(stream)"
                  @click="forceStopRecording(stream)" 
                  class="btn btn-danger action-btn"
                  title="Stop Recording"
                  :disabled="stoppingRecordingStreamerId === stream.streamer_id"
                  :aria-label="`Stop recording ${stream.title || 'stream'} (currently recording)`"
                >
                  <span v-if="stoppingRecordingStreamerId === stream.streamer_id">
                    <i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Stopping...
                  </span>
                  <span v-else>
                    <i class="fas fa-stop" aria-hidden="true"></i> Stop Recording
                  </span>
                </button>
              </div>
              
              <!-- Secondary Actions -->
              <div class="secondary-actions">
                <!-- Details Toggle Button -->
                <!-- Details Toggle Button -->
                <button 
                  @click="toggleDetails(stream.id)" 
                  class="btn btn-secondary details-toggle"
                  :title="expandedStreams.has(stream.id) ? 'Hide details' : 'Show details'"
                  :aria-label="`${expandedStreams.has(stream.id) ? 'Hide' : 'Show'} details for ${stream.title || 'stream'}`"
                  :aria-expanded="expandedStreams.has(stream.id)"
                  :aria-controls="`stream-details-${stream.id}`"
                >
                  <i 
                    :class="['fas', expandedStreams.has(stream.id) ? 'fa-chevron-up' : 'fa-chevron-down']" 
                    aria-hidden="true"
                  ></i>
                  {{ expandedStreams.has(stream.id) ? 'Hide Details' : 'Show Details' }}
                </button>                <!-- Delete Stream Button -->
                <button 
                  @click="confirmDeleteStream(stream)" 
                  class="btn btn-danger action-btn" 
                  :disabled="deletingStreamId === stream.id || (!stream.ended_at && isStreamBeingRecorded(stream))"
                  title="Delete Stream"
                  :aria-label="`Delete stream ${stream.title || 'Untitled Stream'} - this action cannot be undone`"
                >
                  <span v-if="deletingStreamId === stream.id">
                    <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
                  </span>
                  <span v-else>
                    <i class="fas fa-trash" aria-hidden="true"></i>
                  </span>
                </button>
              </div>
            </div>
          </div>
          
          <!-- Expanded Details -->
          <div 
            v-if="expandedStreams.has(stream.id)" 
            class="stream-details"
            :id="`stream-details-${stream.id}`"
          >
            <div class="details-sections">
              <!-- Basic Information Section -->
              <div class="details-section">
                <h4 class="section-title">
                  <i class="fas fa-info-circle"></i> Stream Information
                </h4>
                <div class="details-grid">
                  <div class="detail-item">
                    <span class="detail-label">Duration:</span>
                    <span class="detail-value">{{ calculateDuration(stream) }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Started:</span>
                    <span class="detail-value">{{ formatDate(stream.started_at) }}</span>
                  </div>
                  <div v-if="stream.ended_at" class="detail-item">
                    <span class="detail-label">Ended:</span>
                    <span class="detail-value">{{ formatDate(stream.ended_at) }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Language:</span>
                    <span class="detail-value">{{ stream.language || 'Unknown' }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Stream ID:</span>
                    <span class="detail-value">{{ stream.id }}</span>
                  </div>
                  <div v-if="stream.twitch_stream_id" class="detail-item">
                    <span class="detail-label">Twitch Stream ID:</span>
                    <span class="detail-value">{{ stream.twitch_stream_id }}</span>
                  </div>
                </div>
              </div>

              <!-- Categories Section -->
              <div class="details-section">
                <h4 class="section-title">
                  <i class="fas fa-tags"></i> Categories
                </h4>
                <div class="categories-container">
          <template v-if="getCategoryHistory(stream).length > 0">
                    <div
                      v-for="(cat, idx) in getCategoryHistory(stream)"
                      :key="`${cat.timestamp}-${idx}`"
                      class="category-item"
                    >
                      <div class="category-image-wrapper">
                        <template v-if="getCategoryImageSrc(cat.name).startsWith('icon:')">
                          <div class="category-icon-small">
                            <i :class="`fas ${getCategoryImageSrc(cat.name).replace('icon:', '')}`"></i>
                          </div>
                        </template>
                        <template v-else>
                          <img
                            :src="getCategoryImageSrc(cat.name)"
                            :alt="cat.name"
                            @error="handleImageError($event, cat.name)"
                            loading="lazy"
                            class="category-image-small"
                          />
                        </template>
                      </div>
                      <div class="category-info">
                        <span class="category-name">{{ cat.name }}</span>
                        <span v-if="cat.duration" class="category-duration">
                          {{ formatDuration(cat.duration) }}
                        </span>
                      </div>
                    </div>
                  </template>
                  <div v-else class="no-categories">
                    <i class="fas fa-question-circle"></i>
                    <span>No category information available</span>
                  </div>
                </div>
              </div>

              <!-- Chapters Section -->
              <div class="details-section">
                <h4 class="section-title">
                  <i class="fas fa-list-ol"></i> Chapter Timeline
                </h4>
                <div v-if="getChaptersState(stream.id).isLoading" class="chapters-loading">
                  <i class="fas fa-spinner fa-spin"></i> Loading chapters...
                </div>
                <div v-else-if="getChaptersState(stream.id).error" class="chapters-error">
                  <i class="fas fa-exclamation-triangle"></i> {{ getChaptersState(stream.id).error }}
                </div>
                <div v-else>
                  <div v-if="getChaptersState(stream.id).chapters.length === 0" class="no-chapters">
                    <i class="fas fa-info-circle"></i> No chapters available
                  </div>
                  <ul v-else class="chapters-list">
                    <li v-for="(ch, idx) in getChaptersState(stream.id).chapters" :key="idx" class="chapter-item">
                      <span class="chapter-time">{{ formatChapterStart(ch.start_time, stream.started_at) }}</span>
                      <span class="chapter-title">{{ ch.title || 'Chapter' }}</span>
                    </li>
                  </ul>
                </div>
              </div>

              <!-- Recording Status Section -->
              <div class="details-section">
                <h4 class="section-title">
                  <i class="fas fa-video"></i> Recording Status
                </h4>
                <div class="recording-status-details">
                  <div class="status-item">
                    <span class="status-label">Current Status:</span>
                    <span class="status-value">
                      <span v-if="!stream.ended_at">
                        <span v-if="isStreamBeingRecorded(stream)" class="status-recording">
                          <i class="fas fa-record-vinyl recording-pulse"></i> Currently Recording
                        </span>
                        <span v-else class="status-not-recording">
                          <i class="fas fa-circle-o"></i> Not Recording
                        </span>
                      </span>
                      <span v-else>
                        <span class="status-ended">
                          <i class="fas fa-stop-circle"></i> Stream Ended
                        </span>
                      </span>
                    </span>
                  </div>
                  <div class="status-item">
                    <span class="status-label">Recording Available:</span>
                    <span class="status-value">
                      <span v-if="hasRecording(stream)" class="status-available">
                        <i class="fas fa-check-circle"></i> Yes
                      </span>
                      <span v-else class="status-unavailable">
                        <i class="fas fa-times-circle"></i> No
                      </span>
                    </span>
                  </div>
                  <div v-if="stream.recording_path" class="status-item">
                    <span class="status-label">Recording Path:</span>
                    <span class="status-value recording-path" :title="getDisplayPath(stream.recording_path)">
                      {{ getDisplayPath(stream.recording_path) }}
                    </span>
                  </div>
                  <div v-if="(stream as ExtendedStream).recordings && (stream as ExtendedStream).recordings!.length > 0" class="status-item">
                    <span class="status-label">Recording Files:</span>
                    <span class="status-value">{{ (stream as ExtendedStream).recordings!.length }} file(s)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteModal" class="modal-overlay" @click.self="cancelDelete">
      <div class="modal">
        <div class="modal-header">
          <h3>Delete Stream</h3>
          <button 
            @click="cancelDelete" 
            class="close-btn"
            aria-label="Close delete confirmation dialog"
          >
            ×
          </button>
        </div>
        <div class="modal-body">
          <p>Are you sure you want to delete this stream?</p>
          <div v-if="streamToDelete" class="stream-preview">
            <p><strong>Title:</strong> {{ streamToDelete.title || 'Untitled' }}</p>
            <p><strong>Date:</strong> {{ formatDate(streamToDelete.started_at) }}</p>
            <p><strong>Category:</strong> {{ streamToDelete.category_name || 'Unknown' }}</p>
          </div>
          <p class="warning">⚠️ This action cannot be undone and will delete all associated files.</p>
        </div>
        <div class="modal-actions">
          <button 
            @click="cancelDelete" 
            class="btn btn-secondary"
            aria-label="Cancel stream deletion"
          >
            Cancel
          </button>
          <button 
            @click="deleteStream" 
            class="btn btn-danger" 
            :disabled="deletingStreamId !== null"
            :aria-label="`Confirm deletion of stream ${streamToDelete?.title || 'Untitled'} - this action cannot be undone`"
          >
            {{ deletingStreamId !== null ? '⏳ Deleting...' : '🗑️ Delete Stream' }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- Delete All Confirmation Modal -->
    <div v-if="showDeleteAllModal" class="modal-overlay" @click.self="cancelDeleteAll">
      <div class="modal">
        <div class="modal-header">
          <h3>Delete All Streams</h3>
          <button 
            @click="cancelDeleteAll" 
            class="close-btn"
            aria-label="Close delete all confirmation dialog"
          >
            ×
          </button>
        </div>
        <div class="modal-body">
          <p>Delete <strong>ALL {{ streams.length }} streams</strong> for this streamer?</p>
          <p class="warning">⚠️ Active recordings will be skipped to avoid data loss. All other stream records and files will be permanently deleted.</p>
        </div>
        <div class="modal-actions">
          <button 
            @click="cancelDeleteAll" 
            class="btn btn-secondary"
            aria-label="Cancel delete all operation"
          >
            Cancel
          </button>
          <button 
            @click="deleteAllStreams" 
            class="btn btn-danger" 
            :disabled="deletingAllStreams"
            :aria-label="`Confirm deletion of all ${streams.length} streams - this action cannot be undone`"
          >
            {{ deletingAllStreams ? '⏳ Deleting...' : '🗑️ Delete All Streams' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStreams } from '@/composables/useStreams'
import { useSystemAndRecordingStatus } from '@/composables/useSystemAndRecordingStatus'
import { useCategoryImages } from '@/composables/useCategoryImages'
import { useForceRecording } from '@/composables/useForceRecording'
import { recordingApi, streamsApi, streamersApi } from '@/services/api'
import type { Stream } from '@/types/streams'

// Extend the base Stream interface with additional properties
interface StreamCategory {
  name: string
  duration?: number
}

interface StreamRecording {
  id: number
  file_path: string
  file_size?: number
  created_at: string
}

interface ExtendedStream extends Stream {
  categories?: StreamCategory[]
  recordings?: StreamRecording[]
}

// Type guard to check if stream has required properties
const hasValidStartDate = (stream: Stream): stream is Stream & { started_at: string } => {
  return stream.started_at !== null
}

// Define props
interface Props {
  hideHeader?: boolean
  streamerId?: string
  streamerName?: string
}

const props = withDefaults(defineProps<Props>(), {
  hideHeader: false,
  streamerId: '',
  streamerName: ''
})

const route = useRoute()
const router = useRouter()

// Use props or route parameters
const streamerId = computed(() => props.streamerId || route.params.id as string || route.query.id as string)
const streamerName = computed(() => props.streamerName || route.query.name as string)

const { streams, isLoading, fetchStreams } = useStreams()
const { activeRecordings } = useSystemAndRecordingStatus()
const { getCategoryImage, preloadCategoryImages } = useCategoryImages()
const { forceRecordingStreamerId, forceStartRecording } = useForceRecording()

// UI State
const expandedStreams = ref<Set<number>>(new Set())
const deletingStreamId = ref<number | null>(null)
const deletingAllStreams = ref(false)
const showDeleteModal = ref(false)
const showDeleteAllModal = ref(false)
const streamToDelete = ref<ExtendedStream | null>(null)
const stoppingRecordingStreamerId = ref<number | null>(null)

// WebSocket State for real-time updates
const localRecordingState = ref<Record<number, boolean>>({})

// Chapters state per stream
type Chapter = { start_time: string; title?: string; type?: string }
type ChapterState = { isLoading: boolean; error: string | null; chapters: Chapter[] }
const chaptersByStreamId = ref<Record<number, ChapterState>>({})

const getChaptersState = (streamId: number): ChapterState => {
  if (!chaptersByStreamId.value[streamId]) {
    chaptersByStreamId.value[streamId] = { isLoading: false, error: null, chapters: [] }
  }
  return chaptersByStreamId.value[streamId]
}

const loadChapters = async (s: Stream) => {
  const state = getChaptersState(s.id)
  if (state.isLoading || state.chapters.length > 0) return
  state.isLoading = true
  state.error = null
  try {
    const res = await streamersApi.getStreamChapters(Number(s.streamer_id), Number(s.id))
    const arr = Array.isArray(res?.chapters) ? res.chapters : []
    state.chapters = arr
  } catch (_e: any) {
    state.error = 'Failed to load chapters'
  } finally {
    state.isLoading = false
  }
}

// Wrapper for force start recording with local state update
const forceStartRecordingWithLocalUpdate = async (streamerId: number) => {
  await forceStartRecording(streamerId, (streamerId: number) => {
    // Update local recording state immediately
  const activeStream = streams.value.find((s: Stream) => s.streamer_id === streamerId && !s.ended_at)
    if (activeStream) {
      localRecordingState.value[activeStream.id] = true
    }
  })
}

// Computed Properties
const sortedStreams = computed(() => {
  return [...streams.value].sort((a, b) => {
    // Live streams first
    if (!a.ended_at && b.ended_at) return -1
    if (a.ended_at && !b.ended_at) return 1
    
    // Then by start date (newest first)
    const aDate = a.started_at ? new Date(a.started_at).getTime() : 0
    const bDate = b.started_at ? new Date(b.started_at).getTime() : 0
    return bDate - aDate
  })
})

// Check if a specific stream is being recorded
const isStreamBeingRecorded = (stream: Stream): boolean => {
  if (!stream || stream.ended_at) return false

  const streamId = Number(stream.id)
  const streamerId = Number(stream.streamer_id)

  // Check local WebSocket state first
  if (localRecordingState.value[streamId] !== undefined) {
    return localRecordingState.value[streamId]
  }

  // Check active recordings
  if (!activeRecordings.value || !Array.isArray(activeRecordings.value)) {
    return false
  }

  // Prefer exact stream_id match when available, otherwise fall back to streamer_id
  return activeRecordings.value.some((rec: any) => {
    const recStreamId = rec.stream_id != null ? Number(rec.stream_id) : null
    if (recStreamId != null && !Number.isNaN(recStreamId)) {
      return recStreamId === streamId
    }
    const recStreamerId = Number(rec.streamer_id)
    return recStreamerId === streamerId
  })
}

// Utility Functions
const getCategoryImageSrc = (categoryName: string): string => {
  const imageUrl = getCategoryImage(categoryName)
  return imageUrl || 'icon:fa-gamepad'
}

const getDisplayPath = (recordingPath: string): string => {
  if (!recordingPath) return ''
  
  // Extract filename from path and add .mp4 extension if missing
  const filename = recordingPath.split(/[\/\\]/).pop() || recordingPath
  
  // Add .mp4 extension if not present
  if (!filename.toLowerCase().endsWith('.mp4')) {
    return filename + '.mp4'
  }
  
  return filename
}

const handleImageError = (event: Event, _categoryName: string) => {
  const target = event.target as HTMLImageElement
  target.style.display = 'none'
  
  const wrapper = target.parentElement
  if (wrapper) {
    // Use safer DOM methods instead of innerHTML to prevent XSS
    const iconDiv = document.createElement('div')
    iconDiv.className = 'category-icon'
    const icon = document.createElement('i')
    icon.className = 'fas fa-gamepad'
    iconDiv.appendChild(icon)
    wrapper.replaceChildren(iconDiv)
  }
}

// Extract all unique categories from a list of streams (main + events)
const extractCategoriesFromStreams = (list: Stream[]): string[] => {
  const set = new Set<string>()
  list.forEach((s: any) => {
    if (s?.category_name) set.add(s.category_name)
    const evs = (s?.events || []) as Array<{ category_name?: string | null }>
    evs.forEach(e => { if (e?.category_name) set.add(e.category_name) })
  })
  return Array.from(set)
}

// Build a category history list from stream events with durations
type CategoryHistoryItem = { name: string; timestamp?: string; duration?: number }
const getCategoryHistory = (s: Stream): CategoryHistoryItem[] => {
  const events = ((s as any).events || []) as Array<{ event_type?: string; category_name?: string | null; timestamp?: string | null }>
  const relevant = events
    .filter(e => !!e && (e.event_type === 'channel.update' || e.event_type === 'stream.online') && e.category_name)
    .sort((a, b) => {
      const at = a.timestamp ? new Date(a.timestamp).getTime() : 0
      const bt = b.timestamp ? new Date(b.timestamp).getTime() : 0
      return at - bt
    })

  if (relevant.length === 0) {
    return s.category_name ? [{ name: s.category_name }] : []
  }

  // Deduplicate consecutive same categories
  const items: CategoryHistoryItem[] = []
  for (const ev of relevant) {
    const name = ev.category_name as string
    if (items.length === 0 || items[items.length - 1].name !== name) {
      items.push({ name, timestamp: ev.timestamp || undefined })
    }
  }

  // Compute durations between changes (ms)
  for (let i = 0; i < items.length; i++) {
    const curr = items[i]
    const next = items[i + 1]
    const startMs = curr.timestamp ? new Date(curr.timestamp).getTime() : (s.started_at ? new Date(s.started_at).getTime() : NaN)
    const endMs = next?.timestamp ? new Date(next.timestamp!).getTime() : (s.ended_at ? new Date(s.ended_at).getTime() : Date.now())
    if (!Number.isNaN(startMs) && !Number.isNaN(endMs) && endMs >= startMs) {
      curr.duration = endMs - startMs
    }
  }

  return items
}

const formatDate = (dateString: string | null): string => {
  if (!dateString) return 'Unknown'
  const date = new Date(dateString)
  return date.toLocaleDateString('de-DE', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const calculateDuration = (stream: Stream): string => {
  if (!stream.ended_at) return 'Live'
  if (!hasValidStartDate(stream)) return 'Unknown'
  
  const start = new Date(stream.started_at)
  const end = new Date(stream.ended_at)
  const durationMs = end.getTime() - start.getTime()
  const hours = Math.floor(durationMs / (1000 * 60 * 60))
  const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60))
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  } else {
    return `${minutes}m`
  }
}

const formatDuration = (durationMs: number): string => {
  const hours = Math.floor(durationMs / (1000 * 60 * 60))
  const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60))
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  } else {
    return `${minutes}m`
  }
}

const hasRecording = (stream: Stream): boolean => {
  // Check if we have recording_path set
  if (stream.recording_path && stream.recording_path.trim() !== '') {
    return true
  }
  
  // Fallback: Check if we have recordings array with files
  const extendedStream = stream as ExtendedStream
  if (extendedStream.recordings && extendedStream.recordings.length > 0) {
    return true
  }
  
  // No recording found
  return false
}
// UI Actions
const toggleDetails = (streamId: number) => {
  if (expandedStreams.value.has(streamId)) {
    expandedStreams.value.delete(streamId)
  } else {
    expandedStreams.value.add(streamId)
  const s = streams.value.find((s: Stream) => s.id === streamId)
    if (s) loadChapters(s)
  }
}

const handleBack = () => {
  if (props.hideHeader) {
    // In embedded mode, emit event to parent instead of navigating
    // This allows the parent component to handle the navigation
    return
  }
  router.push('/streamers')
}

const watchVideo = (stream: Stream) => {
  // Navigate to video player with stream details
  router.push({
    name: 'VideoPlayer',
    params: {
      streamerId: stream.streamer_id,
      streamId: stream.id
    },
    query: {
      title: stream.title,
      streamerName: streamerName.value
    }
  })
}

// Delete Functions
const confirmDeleteStream = (stream: Stream) => {
  streamToDelete.value = stream as ExtendedStream
  showDeleteModal.value = true
}

const confirmDeleteAllStreams = () => {
  showDeleteAllModal.value = true
}

const deleteStream = async () => {
  if (!streamToDelete.value) return
  
  try {
    deletingStreamId.value = streamToDelete.value.id
    
    const response = await streamsApi.delete(Number(streamToDelete.value.id))
    
    console.log('Stream deleted successfully:', response)
    
    // Remove from local state
  const index = streams.value.findIndex((s: Stream) => s.id === streamToDelete.value!.id)
    if (index > -1) {
      streams.value.splice(index, 1)
    }
    
    cancelDelete()
  } catch (error) {
    console.error('Error deleting stream:', error)
    // Send error notification via WebSocket to backend for toast
    // This will trigger a toast notification instead of an alert
  } finally {
    deletingStreamId.value = null
  }
}

// Helper: format chapter start to HH:MM:SS
const pad2 = (n: number) => (n < 10 ? `0${n}` : `${n}`)
const formatHMS = (totalSeconds: number) => {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = Math.floor(totalSeconds % 60)
  return `${pad2(h)}:${pad2(m)}:${pad2(s)}`
}

const formatChapterStart = (start: string, streamStart: string | null): string => {
  // If already HH:MM:SS.mmm, show HH:MM:SS
  const vttMatch = start.match(/^\d{2}:\d{2}:\d{2}\.\d{3}$/)
  if (vttMatch) {
    const [hh, mm, ssMs] = start.split(':')
    const ss = Math.floor(parseFloat(ssMs))
    return `${hh}:${mm}:${pad2(ss)}`
  }
  // Otherwise assume ISO and compute offset from stream start
  if (streamStart) {
    const abs = new Date(start).getTime()
    const base = new Date(streamStart).getTime()
    if (!isNaN(abs) && !isNaN(base)) {
      const diffSec = Math.max(0, Math.floor((abs - base) / 1000))
      return formatHMS(diffSec)
    }
  }
  // Fallback
  return start
}

const deleteAllStreams = async () => {
  try {
    deletingAllStreams.value = true
    
  const response = await streamersApi.deleteAllStreams(Number(streamerId.value), { excludeActive: true })
    
    console.log('All streams deleted successfully:', response)
    
    // Clear local state
    streams.value = []
    cancelDeleteAll()
    
    // Navigate back to streamers
    router.push('/streamers')
  } catch (error) {
    console.error('Error deleting all streams:', error)
    // Send error notification via WebSocket to backend for toast
    // This will trigger a toast notification instead of an alert
  } finally {
    deletingAllStreams.value = false
  }
}

const cancelDelete = () => {
  showDeleteModal.value = false
  streamToDelete.value = null
}

const cancelDeleteAll = () => {
  showDeleteAllModal.value = false
}

// Force Stop Recording Method
const forceStopRecording = async (stream: Stream) => {
  if (!stream || stream.ended_at) return
  
  const streamerId = Number(stream.streamer_id)
  stoppingRecordingStreamerId.value = streamerId
  
  try {
  // Use streamerId to stop recording (API handles finding the active recording)
  const response = await recordingApi.stopRecording(streamerId)
    
    console.log('Force stop recording successful:', response)
    
    // Update local state immediately
    localRecordingState.value[stream.id] = false
      
    // Success notification will be sent via WebSocket from backend
  } catch (error) {
    console.error('Error force stopping recording:', error)
    
    // Let the backend handle error notifications via WebSocket
    // Error messages will be sent as toast notifications
  } finally {
    stoppingRecordingStreamerId.value = null
  }
}

// Lifecycle
onMounted(async () => {
  if (streamerId.value) {
    await fetchStreams(Number(streamerId.value))
    
  // Preload category images (main + from event history)
  const categories = extractCategoriesFromStreams(streams.value as Stream[])
  await preloadCategoryImages(categories)
  }
})

// Refetch streams when the route/prop streamerId changes to avoid stale/mismatched lists
watch(streamerId, async (newVal: string | undefined, oldVal: string | undefined) => {
  if (newVal && newVal !== oldVal) {
    // Reset local UI state tied to previous streamer
    expandedStreams.value = new Set()
    chaptersByStreamId.value = {}
    localRecordingState.value = {}

    await fetchStreams(Number(newVal))

  // Preload category images for the new set (main + history)
  const categories = extractCategoriesFromStreams(streams.value as Stream[])
  await preloadCategoryImages(categories)
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.streams-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--spacing-5);
  background: var(--background-primary);
  min-height: 100vh;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-color);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: var(--spacing-15) var(--spacing-5);
  background: var(--background-card);
  border-radius: var(--border-radius);
  border: 1px solid var(--border-color);
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 20px;
}

.empty-state h3 {
  margin: 0 0 10px 0;
  color: var(--text-primary);
}

.empty-state p {
  color: var(--text-secondary);
  margin-bottom: 30px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding: var(--spacing-5);
  background: var(--background-card);
  border-radius: var(--border-radius);
  border: 1px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  color: var(--text-primary);
  text-decoration: none;
  transition: all 0.2s;
  cursor: pointer;
}

.back-button:hover {
  background: var(--background-dark);
  border-color: var(--primary-color);
}

.header-info h1 {
  margin: 0;
  font-size: 2rem;
  color: var(--text-primary);
  font-weight: 600;
}

.stream-count {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
}

.stream-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  
  /* Responsive grid - better desktop utilization */
  @media (min-width: 1024px) {
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  }
  
  @media (min-width: 1440px) {
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 24px;
  }
  
  @media (min-width: 1920px) {
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 28px;
  }
}

.stream-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  overflow: hidden;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
}

.stream-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.stream-card.live {
  border-color: var(--danger-color);
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.2);
}

.stream-card.recording {
  border-color: var(--success-color);
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.2);
}

/* New simplified header styles */
.stream-info {
  padding: var(--spacing-5);
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stream-header {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(var(--border-color-rgb, 45, 45, 53), 0.5);
  margin-bottom: 16px;
}

.title-and-badges {
  display: flex;
  flex-direction: column;
  gap: 12px;
  
  /* Desktop: Better layout with more space for title */
  @media (min-width: 768px) {
    flex-direction: row;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
  }
  
  @media (min-width: 1024px) {
    gap: 32px;
  }
}

.stream-title {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text-primary);
  font-weight: 600;
  line-height: 1.4;
  word-wrap: break-word;
  word-break: break-word;
  hyphens: auto;
  flex: 1;
  min-width: 0; /* Allow flex shrinking */
  
  /* Larger on tablet/desktop for better readability */
  @media (min-width: 768px) {
    font-size: 1.5rem;
    line-height: 1.3;
  }
  
  @media (min-width: 1024px) {
    font-size: 1.75rem;
    max-width: 70%; /* Give title 70% of space on desktop */
  }
  
  @media (min-width: 1440px) {
    font-size: 2rem;
  }
}

.stream-meta-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
  align-items: center;
  
  /* Desktop: Align to top and right */
  @media (min-width: 768px) {
    align-self: flex-start;
    margin-top: 2px; /* Slight visual alignment with title */
  }
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--border-radius-lg, 12px);
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
}

.status-badge.live {
  background: var(--danger-color);
  color: var(--text-primary);
}

.status-badge.ended {
  background: var(--text-secondary);
  color: var(--text-primary);
}

.status-badge.recording {
  background: var(--success-color);
  color: var(--text-primary);
}

.status-badge.not-recording {
  background: var(--text-secondary);
  color: var(--text-primary);
}

.status-badge.has-recording {
  background: var(--info-color);
  color: var(--text-primary);
}

.recording-pulse {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.stream-info {
  padding: var(--spacing-5);
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stream-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.title-and-badges {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 15px;
}

.stream-title {
  margin: 0;
  font-size: 1.2rem;
  color: var(--text-primary);
  font-weight: 600;
  line-height: 1.3;
  flex: 1;
  word-wrap: break-word;
  word-break: break-word;
  hyphens: auto;
}

.stream-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.stream-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stream-meta-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.recording-pulse {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Header Actions Styling */
.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header-actions .btn {
  font-weight: 600;
  border: 2px solid transparent;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header-actions .btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

/* Button colors handled by global .btn-* classes in _components.scss */

/* Button Styling */
.stream-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: auto;
  padding-top: var(--spacing-4);
}

.recording-actions, .secondary-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.recording-actions {
  min-height: 40px;
}

.secondary-actions {
  padding-top: var(--spacing-2);
  border-top: 1px solid var(--border-color);
}

.action-btn {
  font-size: 0.85rem;
  padding: var(--spacing-2_5) var(--spacing-3_5);
  border-radius: var(--border-radius, 8px);
  font-weight: 600;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  white-space: nowrap;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.action-btn i {
  margin-right: 6px;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.stream-actions .btn {
  font-size: 0.85rem;
  padding: var(--spacing-2) var(--spacing-3);
  border-radius: var(--border-radius, 8px);
  font-weight: 600;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.stream-actions .btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

/* Button colors handled by global .btn-* classes in _components.scss */

.stream-actions .btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.stream-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.stream-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stream-details {
  border-top: 1px solid var(--border-color);
  padding: var(--spacing-5);
  background: var(--background-darker);
}

/* New details sections styling */
.details-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.details-section {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: var(--spacing-4);
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title i {
  color: var(--primary-color);
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-2) 0;
}

.detail-label {
  font-weight: 500;
  color: var(--text-secondary);
}

.detail-value {
  color: var(--text-primary);
  font-weight: 600;
}

/* Categories Section Styling */
.categories-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: var(--background-darker);
  border-radius: var(--border-radius, 8px);
  border: 1px solid var(--border-color);
}

.category-item.main-category {
  border-color: var(--primary-color);
  background: rgba(99, 102, 241, 0.1);
}

.category-image-wrapper {
  flex-shrink: 0;
  width: 30px;
  height: 40px;
  border-radius: var(--border-radius-sm, 4px);
  overflow: hidden;
  background: var(--background-card);
  display: flex;
  align-items: center;
  justify-content: center;
}

.category-image-small {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.category-icon-small {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 1.2rem;
}

.category-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-name {
  font-weight: 500;
  color: var(--text-primary);
}

.category-type {
  font-size: 0.8rem;
  color: var(--primary-color);
  font-weight: 500;
}

.category-duration {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.additional-categories {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.no-categories {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-style: italic;
}

/* Chapters Section */
.chapters-loading,
.chapters-error,
.no-chapters {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
}

.chapters-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chapter-item {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: var(--spacing-1_5) var(--spacing-2);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius, 8px);
}

.chapter-time {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  color: var(--primary-color);
  min-width: 70px;
}

.chapter-title {
  color: var(--text-primary);
}

/* Recording Status Details */
.recording-status-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-2) 0;
  border-bottom: 1px solid var(--border-color);
}

.status-item:last-child {
  border-bottom: none;
}

.status-label {
  font-weight: 500;
  color: var(--text-secondary);
}

.status-value {
  font-weight: 600;
}

.status-value.recording-path {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

.status-recording {
  color: var(--success-color);
}

.status-not-recording {
  color: var(--text-muted);
}

.status-ended {
  color: var(--text-muted);
}

.status-available {
  color: var(--success-color);
}

.status-unavailable {
  color: var(--danger-color);
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--spacing-2) var(--spacing-4);
  border: none;
  border-radius: var(--border-radius);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-color-hover);
}

.btn-secondary {
  background: var(--background-darker);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--background-dark);
  border-color: var(--primary-color);
}

.btn-danger {
  background: var(--danger-color);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: var(--danger-color-hover);
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}


.modal {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden; /* let body scroll, keep header/actions fixed */
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-5);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--spacing-1);
  line-height: 1;
}

.close-btn:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: var(--spacing-5);
  color: var(--text-primary);
  overflow: auto; /* scroll within body if needed */
}

.stream-preview {
  background: var(--background-darker);
  padding: var(--spacing-4);
  border-radius: var(--border-radius);
  margin: var(--spacing-4) 0;
}

.warning {
  color: var(--danger-color);
  font-weight: 500;
  margin-top: var(--spacing-4);
}

.modal-actions {
  display: flex;
  justify-content: center; /* center the confirm/cancel buttons */
  gap: 12px;
  padding: var(--spacing-5);
  border-top: 1px solid var(--border-color);
  position: sticky; /* keep actions visible */
  bottom: 0;
  background: var(--background-card);
}

/* Responsive Design */
@include m.respond-below('md') {  // < 768px
  .streams-container {
    padding: var(--spacing-4);
  }
  
  .stream-grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-4);
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-4);
  }
  
  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-2_5);
  }
  
  .header-info h1 {
    font-size: 1.5rem;
  }
  
  .stream-actions {
    gap: 6px;
    padding-top: var(--spacing-2_5);
  }
  
  .stream-actions .btn {
    font-size: 0.8rem;
    padding: var(--spacing-1_5) var(--spacing-2_5);
    min-width: 80px;
  }
  
  .details-grid {
    grid-template-columns: 1fr;
  }
  
  .stream-card {
    border-radius: var(--border-radius, 8px);
  }
  
  .stream-info {
    padding: var(--spacing-4);
  }
}
</style>
