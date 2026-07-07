<template>
  <div class="page-view live-player-view fade-in">
    <!-- Loading State -->
    <div v-if="isLoading" class="content-state">
      <LoadingSkeleton type="video" />
      <p class="state-text" role="status" aria-live="polite">Starting live stream...</p>
    </div>

    <!-- Stopped State -->
    <div v-else-if="isStopped" class="content-state">
      <EmptyState
        icon="square"
        title="Stream Stopped"
        description="The live stream has been stopped."
        action-label="Back to Streamers"
        action-icon="arrow-left"
        @action="goBack"
      />
    </div>

    <!-- Error State -->
    <div v-else-if="error && !sessionId" class="content-state">
      <PlayerError
        title="Stream Error"
        :message="error || 'Unknown error occurred'"
        action-label="Retry"
        @action="retryStart"
      />
    </div>

    <!-- Live Player -->
    <div v-else-if="sessionId" class="player-layout">
      <div class="player-main">
        <GlassCard variant="strong" :padding="false" class="player-card">
          <!-- Header -->
          <div class="player-header">
            <button @click="goBack" class="back-button" aria-label="Go back" v-ripple>
              <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
              Back
            </button>

            <h1 class="stream-title">{{ streamerName }}</h1>

            <div v-if="streamInfo" class="live-status-strip" :aria-label="`Live stream status: ${streamStatusText}`">
              <span class="live-status-pill">
                <span class="live-indicator"></span>
                Live
              </span>
              <span>{{ streamStatusText }}</span>
              <span>{{ selectedQualityLabel }}</span>
            </div>
          </div>

          <!-- Video Container -->
          <div class="video-container" :class="{ 'show-controls': showControls }" ref="videoContainer" @click="onVideoContainerClick" @touchstart="onTouchStart">
            <video
              ref="videoElement"
              class="video-element"
              playsinline
              autoplay
              muted
              @waiting="onBuffering"
              @playing="onPlaying"
              @error="onVideoError"
            ></video>

            <!-- Buffering Overlay -->
            <div v-if="isBuffering && !error" class="buffering-overlay">
              <PlayerStatus state="buffering" :message="'Buffering live stream...'" />
            </div>
            <div v-if="isRetrying && !error" class="buffering-overlay">
              <PlayerStatus state="connecting" :message="'Reconnecting...'" :retry-count="retryCount" />
            </div>

            <!-- Controls Overlay -->
            <div class="live-controls-overlay">
              <div class="controls-bottom">
                <button @click="togglePlayPause" class="control-button" :aria-label="isPlaying ? 'Pause live stream' : 'Play live stream'">
                  <svg v-if="isPlaying" viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                </button>

                <button @click="toggleMute" class="control-button" :aria-label="isMuted ? 'Unmute live stream' : 'Mute live stream'">
                  <svg v-if="!isMuted" viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                    <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3z"/>
                  </svg>
                </button>

                <div class="stream-meta">
                  <span class="meta-quality">{{ selectedQualityLabel }}</span>
                  <span class="meta-separator">|</span>
                  <span class="meta-status">{{ streamStatusText }}</span>
                </div>

                <button @click="toggleFullscreen" class="control-button fullscreen-button" :aria-label="isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'">
                  <svg v-if="!isFullscreen" viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                    <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                    <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </GlassCard>

        <!-- Info Sidebar -->
        <aside class="info-sidebar">
          <GlassCard variant="subtle" class="info-card">
            <h2 class="info-title">
              <svg class="info-icon">
                <use href="#icon-info" />
              </svg>
              Stream Info
            </h2>
            <div class="info-list">
              <div class="info-row">
                <span class="info-label">Streamer</span>
                <span class="info-value highlight">{{ streamerName }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Session</span>
                <span class="info-value">{{ sessionIdShort }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Quality</span>
                <span class="info-value">{{ selectedQualityLabel }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Codec Mode</span>
                <span class="info-value">{{ codecModeLabel }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Codecs</span>
                <span class="info-value">{{ activeSupportedCodecs }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Status</span>
                <span class="info-value" :class="{ 'text-live': isPlaying && !isBuffering }">
                  {{ streamStatusText }}
                </span>
              </div>
            </div>
          </GlassCard>

          <GlassCard variant="subtle" class="info-card">
            <h2 class="info-title">
              <svg class="info-icon">
                <use href="#icon-settings" />
              </svg>
              Actions
            </h2>
            <div class="action-buttons">
              <label class="codec-selector">
                <span class="codec-selector-label">Live codec</span>
                <select
                  v-model="codecMode"
                  class="codec-select"
                  :disabled="isLoading || isStopping"
                  @change="restartWithCodecMode"
                >
                  <option value="auto">Auto detect</option>
                  <option value="h264">H264 compatibility</option>
                  <option value="hevc">HEVC/1440p experimental</option>
                </select>
              </label>
              <p class="codec-hint">{{ codecHint }}</p>

              <button class="action-btn danger" @click="stopStream" :disabled="isStopping" v-ripple>
                <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                </svg>
                {{ isStopping ? 'Stopping...' : 'Stop Stream' }}
              </button>
            </div>
          </GlassCard>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import GlassCard from '@/components/cards/GlassCard.vue'
import PlayerStatus from '@/components/player/PlayerStatus.vue'
import PlayerError from '@/components/player/PlayerError.vue'
import { liveApi } from '@/services/api'
import { appStorage } from '@/services/storage'

// Hls.js type declaration (loaded via npm, no longer from CDN)
declare global {
  interface Window {
    Hls?: any
  }
}

interface HlsLevel {
  height?: number
  width?: number
  bitrate?: number
}

type LiveCodecMode = 'auto' | 'h264' | 'hevc'

interface LiveCodecSelection {
  supportedCodecs: string
  useNativeHls: boolean
  hevcSupported: boolean
}

const route = useRoute()
const router = useRouter()

const streamerName = computed(() => route.params.streamer as string)

// Reactive state
const isLoading = ref(true)
const error = ref<string | null>(null)
const sessionId = ref<string | null>(null)
const streamInfo = ref<any>(null)
const isStopping = ref(false)
const isStopped = ref(false)
const isStarting = ref(false)
const isBuffering = ref(false)
const isPlaying = ref(false)
const isRetrying = ref(false)
const isMuted = ref(true)
const isFullscreen = ref(false)
const showControls = ref(true)
const controlsTimeout = ref<number | null>(null)
const hlsInstance = ref<any>(null)
const qualityLevels = ref<Array<{ name: string; index: number }>>([])
const selectedQuality = ref<string | number>('-1')
const retryCount = ref(0)
const retryTimer = ref<number | null>(null)
const codecMode = ref<LiveCodecMode>(
  ((route.query.codec as LiveCodecMode) ||
    appStorage.liveCodecMode ||
    'auto') as LiveCodecMode
)
const activeSupportedCodecs = ref('h264')
const preferNativeHls = ref(false)
const hevcSupported = ref(false)

// Refs
const videoElement = ref<HTMLVideoElement | null>(null)
const videoContainer = ref<HTMLDivElement | null>(null)

const sessionIdShort = computed(() => {
  if (!sessionId.value) return ''
  return sessionId.value.length > 12 ? sessionId.value.slice(0, 12) + '...' : sessionId.value
})

const selectedQualityLabel = computed(() => {
  if (selectedQuality.value === '-1') {
    const requestedQuality = streamInfo.value?.quality
    return requestedQuality && requestedQuality !== 'best' ? requestedQuality : 'Auto'
  }
  const level = qualityLevels.value.find(l => l.index === Number(selectedQuality.value))
  return level ? level.name : 'Auto'
})

const streamStatusText = computed(() => {
  if (isStopped.value) return 'Stopped'
  if (isRetrying.value) return 'Reconnecting'
  if (isBuffering.value) return 'Buffering'
  if (isPlaying.value) return 'Live'
  return 'Connecting'
})

const codecModeLabel = computed(() => {
  if (codecMode.value === 'h264') return 'H264 compatibility'
  if (codecMode.value === 'hevc') return 'HEVC/1440p experimental'
  return hevcSupported.value ? 'Auto (HEVC enabled)' : 'Auto (H264 fallback)'
})

const codecHint = computed(() => {
  if (codecMode.value === 'h264') {
    return 'Most compatible; caps live playback to H264-compatible qualities.'
  }
  if (codecMode.value === 'hevc') {
    return 'Tries Twitch HEVC/1440p. If video is black, switch back to H264.'
  }
  return hevcSupported.value
    ? 'HEVC appears supported here; Auto will allow 1440p/HEVC.'
    : 'HEVC is not supported by this playback pipeline; Auto uses H264.'
})

const hlsErrorToMessage = (data: any): string => {
  if (!data || !data.type) return 'Stream playback failed'
  const type = data.type
  const details = data.details || ''
  if (type === 'networkError') {
    if (details.includes('manifestLoadError') || details.includes('levelLoadError')) {
      return 'Unable to load the live stream. The streamer may be offline or the stream may have ended.'
    }
    if (details.includes('timeout')) {
      return 'Connection to the live stream timed out. Check your network and try again.'
    }
    return 'Network error during stream playback. Please check your connection.'
  }
  if (type === 'mediaError') {
    return 'An audio or video playback error occurred. Trying to recover...'
  }
  if (type === 'muxError') {
    return 'The stream data could not be processed. This may be a codec compatibility issue.'
  }
  if (type === 'otherError') {
    return 'An unexpected stream error occurred. Please try reconnecting.'
  }
  return 'Stream playback failed. Please try again.'
}

// Load hls.js (bundled locally, no CDN dependency)
import Hls from 'hls.js'

const loadHlsJs = (): Promise<any> => {
  return Promise.resolve(Hls)
}

const getStoredSessionToken = (): string | null => {
  return appStorage.sessionToken
}

const canUseNativeHls = (): boolean => {
  const video = document.createElement('video')
  return Boolean(video.canPlayType('application/vnd.apple.mpegurl'))
}

const canUseHevcWithMse = (): boolean => {
  if (typeof MediaSource === 'undefined') return false

  const hevcCodecStrings = [
    'video/mp4; codecs="hvc1.1.6.L120.90, mp4a.40.2"',
    'video/mp4; codecs="hev1.1.6.L120.90, mp4a.40.2"',
    'video/mp4; codecs="hvc1.1.6.L123.B0, mp4a.40.2"',
    'video/mp4; codecs="hev1.1.6.L123.B0, mp4a.40.2"'
  ]

  return hevcCodecStrings.some(codec => MediaSource.isTypeSupported(codec))
}

const resolveLiveCodecSelection = (): LiveCodecSelection => {
  const nativeHls = canUseNativeHls()
  const mseHevc = canUseHevcWithMse()
  const supportsHevc = nativeHls || mseHevc
  const mode = ['auto', 'h264', 'hevc'].includes(codecMode.value)
    ? codecMode.value
    : 'auto'

  hevcSupported.value = supportsHevc

  if (mode === 'h264') {
    return { supportedCodecs: 'h264', useNativeHls: false, hevcSupported: supportsHevc }
  }

  if (mode === 'hevc') {
    return { supportedCodecs: 'h264,h265', useNativeHls: nativeHls, hevcSupported: supportsHevc }
  }

  return supportsHevc
    ? { supportedCodecs: 'h264,h265', useNativeHls: nativeHls, hevcSupported: supportsHevc }
    : { supportedCodecs: 'h264', useNativeHls: false, hevcSupported: supportsHevc }
}

// Start stream
const startStream = async () => {
  if (isStarting.value) return

  try {
    isStarting.value = true
    isLoading.value = true
    error.value = null
    isStopped.value = false
    isRetrying.value = false
    retryCount.value = 0
    sessionId.value = null

    const quality = (route.query.quality as string) || 'best'
    const codecSelection = resolveLiveCodecSelection()
    activeSupportedCodecs.value = codecSelection.supportedCodecs
    preferNativeHls.value = codecSelection.useNativeHls
    appStorage.setLiveCodecMode(codecMode.value)

    const response = await liveApi.startLiveStream(
      streamerName.value,
      quality,
      codecSelection.supportedCodecs
    )

    if (!response.success || !response.session_id) {
      throw new Error(response.message || 'Failed to start stream')
    }

    sessionId.value = response.session_id
    streamInfo.value = response

    // CRITICAL FIX: Set loading false BEFORE initPlayer so videoElement exists in DOM
    isLoading.value = false

    // Wait for Vue to render the player block (videoElement must exist)
    await nextTick()

    // Small delay to ensure HLS playlist exists on backend
    await new Promise(r => setTimeout(r, 1500))

    await initPlayer(response.session_id, codecSelection.useNativeHls)
  } catch (err: any) {
    console.error('Error starting stream:', err)
    error.value = err instanceof Error ? err.message : 'Failed to start live stream'
    sessionId.value = null
    streamInfo.value = null
  } finally {
    // Ensure loading is cleared in error cases too (success path clears it above)
    if (!sessionId.value) {
      isLoading.value = false
    }
    isStarting.value = false
  }
}

// Initialize HLS player
const initPlayer = async (sid: string, useNativeHls: boolean = preferNativeHls.value) => {
  if (!videoElement.value) return

  try {
    const Hls = await loadHlsJs()
    const playlistUrl = streamInfo.value?.playlist_url || liveApi.getPlaylistUrl(sid)

    if (useNativeHls && videoElement.value.canPlayType('application/vnd.apple.mpegurl')) {
      // Native HLS is preferred for HEVC-capable Safari/WebKit pipelines.
      hlsInstance.value = null
      videoElement.value.src = playlistUrl
      videoElement.value.addEventListener('loadedmetadata', () => {
        videoElement.value?.play().catch(() => {})
      }, { once: true })
    } else if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 90,
        maxBufferLength: 30,
        liveSyncDurationCount: 3,
        liveMaxLatencyDurationCount: 5,
        xhrSetup: (xhr: XMLHttpRequest) => {
          xhr.withCredentials = true
          const sessionToken = getStoredSessionToken()
          if (sessionToken) {
            xhr.setRequestHeader('Authorization', `Bearer ${sessionToken}`)
          }
        },
      })

      hlsInstance.value = hls

      hls.on(Hls.Events.MANIFEST_PARSED, (_event: string, data: any) => {
        isBuffering.value = false
        // StreamVault remuxes one selected Twitch rendition into a local HLS stream.
        // hls.js can report that single remuxed rendition as height=0 because the
        // generated playlist has no adaptive RESOLUTION metadata. Do not surface
        // those pseudo-levels as a broken "0p" quality picker.
        const levels: Array<{ name: string; index: number }> = []
        if (data.levels) {
          data.levels.forEach((level: HlsLevel, index: number) => {
            const height = level.height || 0
            if (height <= 0) return
            const name = height >= 1080 ? '1080p' : height >= 720 ? '720p' : height >= 480 ? '480p' : `${height}p`
            levels.push({ name, index })
          })
        }
        qualityLevels.value = levels
        videoElement.value?.play().catch(() => {})
      })

      hls.on(Hls.Events.ERROR, (_event: string, data: any) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              console.warn('HLS network error, attempting recovery...')
              isRetrying.value = true
              retryCount.value++
              hls.startLoad()
              break
            case Hls.ErrorTypes.MEDIA_ERROR:
              console.warn('HLS media error, attempting recovery...')
              isRetrying.value = true
              retryCount.value++
              hls.recoverMediaError()
              break
            default:
              console.error('Fatal HLS error:', data)
              error.value = hlsErrorToMessage(data)
              sessionId.value = null
              destroyPlayer()
              break
          }
        }
      })

      hls.on(Hls.Events.LEVEL_SWITCHED, (_event: string, data: any) => {
        console.log('Quality switched to level', data.level)
      })

      hls.loadSource(playlistUrl)
      hls.attachMedia(videoElement.value)
    } else if (videoElement.value.canPlayType('application/vnd.apple.mpegurl')) {
      // Native HLS support (Safari)
      videoElement.value.src = playlistUrl
      videoElement.value.addEventListener('loadedmetadata', () => {
        videoElement.value?.play().catch(() => {})
      })
    } else {
      throw new Error('HLS is not supported in this browser')
    }
  } catch (err: any) {
    console.error('Error initializing player:', err)
    error.value = err instanceof Error ? err.message : 'Failed to initialize player'
    isRetrying.value = false
    sessionId.value = null
    streamInfo.value = null
    destroyPlayer()
  }
}

// Destroy player and cleanup
const destroyPlayer = () => {
  if (hlsInstance.value) {
    hlsInstance.value.destroy()
    hlsInstance.value = null
  }
  if (videoElement.value) {
    videoElement.value.pause()
    videoElement.value.removeAttribute('src')
    videoElement.value.load()
  }
  qualityLevels.value = []
}

// Stop stream
const stopStream = async () => {
  if (!sessionId.value || isStopping.value) return

  try {
    isStopping.value = true
    showControls.value = true
    destroyPlayer()
    await liveApi.stopLiveStream(sessionId.value)
    sessionId.value = null
    streamInfo.value = null
    isStopped.value = true
    isPlaying.value = false
    isBuffering.value = false
  } catch (err: any) {
    console.error('Error stopping stream:', err)
    error.value = err instanceof Error ? err.message : 'Failed to stop stream'
  } finally {
    isStopping.value = false
  }
}

// Retry start
const retryStart = () => {
  if (retryTimer.value) {
    clearTimeout(retryTimer.value)
    retryTimer.value = null
  }
  startStream()
}

const restartWithCodecMode = async () => {
  if (isStarting.value || isStopping.value) return

  appStorage.setLiveCodecMode(codecMode.value)
  router.replace({
    query: {
      ...route.query,
      codec: codecMode.value
    }
  }).catch(() => {})

  const currentSessionId = sessionId.value
  destroyPlayer()
  sessionId.value = null
  streamInfo.value = null
  isPlaying.value = false
  isBuffering.value = false

  if (currentSessionId) {
    await liveApi.stopLiveStream(currentSessionId).catch(() => {})
  }

  await startStream()
}

// Auto-retry logic
const scheduleRetry = () => {
  if (retryCount.value >= 10) {
    error.value = 'Stream could not be started after multiple attempts. The streamer may be offline.'
    isRetrying.value = false
    return
  }
  retryCount.value++
  isRetrying.value = true
  retryTimer.value = window.setTimeout(() => {
    if (!isPlaying.value && sessionId.value) {
      console.log(`Auto-retry attempt ${retryCount.value}...`)
      initPlayer(sessionId.value)
    }
  }, 3000)
}

// Video event handlers
const onBuffering = () => {
  isBuffering.value = true
}

const onPlaying = () => {
  isBuffering.value = false
  isPlaying.value = true
  isRetrying.value = false
  showControls.value = true
  resetControlsTimeout()
}

const onVideoError = () => {
  console.error('Video element error')
  isBuffering.value = false
  isPlaying.value = false
  isRetrying.value = true
  scheduleRetry()
}

const resetControlsTimeout = () => {
  if (controlsTimeout.value) {
    clearTimeout(controlsTimeout.value)
  }
  if (isPlaying.value) {
    const delay = window.innerWidth < 768 ? 5000 : 3000
    controlsTimeout.value = window.setTimeout(() => {
      showControls.value = false
    }, delay)
  }
}

const onVideoContainerClick = () => {
  if (!showControls.value) {
    showControls.value = true
    resetControlsTimeout()
  }
}

const onTouchStart = () => {
  showControls.value = true
  resetControlsTimeout()
}

// Controls
const togglePlayPause = () => {
  if (!videoElement.value) return
  if (videoElement.value.paused) {
    videoElement.value.play().catch(() => {})
  } else {
    videoElement.value.pause()
  }
  isPlaying.value = !videoElement.value.paused
}

const toggleMute = () => {
  if (!videoElement.value) return
  videoElement.value.muted = !videoElement.value.muted
  isMuted.value = videoElement.value.muted
}

const toggleFullscreen = async () => {
  if (!videoContainer.value) return
  try {
    if (!document.fullscreenElement) {
      await videoContainer.value.requestFullscreen()
      isFullscreen.value = true
    } else {
      await document.exitFullscreen()
      isFullscreen.value = false
    }
  } catch (err) {
    console.error('Fullscreen error:', err)
  }
}

const goBack = () => {
  router.back()
}

const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  startStream()
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (retryTimer.value) {
    clearTimeout(retryTimer.value)
  }
  if (controlsTimeout.value) {
    clearTimeout(controlsTimeout.value)
  }
  destroyPlayer()
  // Also stop the stream on the backend if still active
  if (sessionId.value) {
    liveApi.stopLiveStream(sessionId.value).catch(() => {})
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.live-player-view {
  overflow-x: hidden;
  max-width: 100%;

  @include m.respond-below('sm') {
    padding: var(--spacing-2) var(--spacing-2);
  }
}

.fade-in {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.content-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 50vh;
  padding: var(--spacing-8);
}

.state-text {
  margin-top: var(--spacing-4);
  color: var(--text-secondary);
  font-size: var(--text-base);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.player-layout {
  display: flex;
  flex-direction: column;
  max-width: 100%;
  overflow: hidden;
}

.player-main {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--spacing-4);
  align-items: start;
  max-width: 100%;
  overflow: hidden;

  @include m.respond-below('xl') {
    grid-template-columns: 1fr 280px;
  }

  @include m.respond-below('lg') {
    grid-template-columns: 1fr;
  }

  @include m.respond-below('sm') {
    gap: var(--spacing-2);
  }
}

.player-card {
  overflow: hidden;

  :deep(.glass-card-content) {
    padding: 0;
    display: flex;
    flex-direction: column;
  }
}

.player-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);

  @include m.respond-below('md') {
    flex-wrap: wrap;
    padding: var(--spacing-3);
  }
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--background-darker);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  font-weight: v.$font-medium;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  flex-shrink: 0;
  min-height: 44px;

  .icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
  }

  @include m.respond-below('md') {
    min-height: 44px;
    padding: var(--spacing-2) var(--spacing-4);
    font-size: var(--text-sm);
  }
}

.stream-title {
  flex: 1;
  margin: 0;
  font-size: var(--text-lg);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  @include m.respond-below('lg') {
    white-space: normal;
    overflow: visible;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  @include m.respond-below('md') {
    font-size: var(--text-base);
    order: 3;
    flex-basis: 100%;
    margin-top: var(--spacing-2);
  }
}

.live-status-strip {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  border: 1px solid rgba(var(--danger-500-rgb), 0.35);
  border-radius: var(--radius-pill);
  background: rgba(var(--danger-500-rgb), 0.12);
  color: var(--text-secondary);
  padding: var(--spacing-1) var(--spacing-2);
  font-size: var(--text-xs);
  font-weight: v.$font-semibold;
  flex-shrink: 0;
}

.live-status-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  color: var(--danger-text-color);
  font-weight: v.$font-bold;
  text-transform: uppercase;
}

.live-indicator {
  width: 8px;
  height: 8px;
  background: white;
  border-radius: 50%;
  animation: pulse-live 2s ease-in-out infinite;
}

@keyframes pulse-live {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.player-state-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-3);
  border-radius: var(--radius-pill);
  font-size: var(--text-xs);
  font-weight: v.$font-semibold;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  flex-shrink: 0;
}

.player-state-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.player-state-dot.dot-live {
  background: var(--danger-color);
  animation: pulse-dot 2s ease-in-out infinite;
}

.player-state-dot.dot-buffering {
  background: var(--warning-color);
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.video-container {
  position: relative;
  width: 100%;
  background: var(--background-darker);
  overflow: hidden;
  border-top: 1px solid var(--border-color);

  @include m.respond-to('md') {
    max-width: none;
    margin: 0;
    aspect-ratio: 16/9;
  }

  @include m.respond-below('md') {
    width: 100%;
    max-width: 100%;
    margin: 0;
    aspect-ratio: 16/9;
  }

  &:fullscreen {
    width: 100vw;
    height: 100vh;
    max-width: none;
    margin: 0;
    aspect-ratio: auto;
    background: var(--background-darker);
  }

  &:fullscreen .video-element {
    width: 100%;
    height: 100%;
    max-height: none;
    object-fit: contain;
  }
}

.video-element {
  width: 100%;
  height: 100%;
  display: block;
  background: var(--background-darker);
  object-fit: contain;

  @include m.respond-to('md') {
    max-height: 70vh;
  }

  @include m.respond-below('md') {
    max-height: none;
  }
}

// Mobile Landscape
@media (max-width: 767px) and (orientation: landscape) {
  .video-container {
    height: 100vh;
    width: auto;
    aspect-ratio: auto;
    margin: 0;
  }

  .video-element {
    height: 100%;
    width: 100%;
    max-height: 100vh;
  }
}

.buffering-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
  z-index: 20;
  gap: var(--spacing-4);

  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid rgba(255, 255, 255, 0.2);
    border-top-color: var(--primary-color);
    border-radius: var(--radius-full);
    animation: spin 1s linear infinite;
  }

  p {
    font-size: var(--text-sm);
    color: rgba(255, 255, 255, 0.8);
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.live-controls-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: var(--spacing-3) var(--spacing-4);
  background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%);
  z-index: 10;
  opacity: 0;
  transition: opacity var(--duration-300) var(--ease-out);

  .video-container:hover &,
  .video-container:focus-within &,
  .video-container.show-controls & {
    opacity: 1;
  }

  @include m.respond-below('md') {
    opacity: 1;
    padding-bottom: calc(var(--spacing-3) + env(safe-area-inset-bottom, 0px));
  }
}

.controls-bottom {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.control-button {
  min-width: 44px;
  min-height: 44px;
  padding: 0;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background v.$duration-200 v.$ease-out;
  color: white;

  &:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  &:focus-visible {
    outline: 2px solid white;
    outline-offset: 2px;
  }

  .control-icon {
    width: 20px;
    height: 20px;
  }
}

.fullscreen-button {
  margin-left: auto;
}

.stream-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  color: rgba(255, 255, 255, 0.8);
  font-size: var(--text-xs);
  font-weight: v.$font-medium;
}

.meta-separator {
  opacity: 0.5;
}

.meta-quality {
  background: rgba(var(--primary-500-rgb), 0.3);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.meta-status {
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.text-live {
  color: var(--danger-color);
}

// Info Sidebar
.info-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  min-width: 0;
  max-width: 100%;

  @include m.respond-below('lg') {
    flex-direction: row;
    flex-wrap: wrap;

    .info-card {
      flex: 1;
      min-width: 280px;
    }
  }

  @include m.respond-below('sm') {
    flex-direction: column;
    gap: var(--spacing-2);

    .info-card {
      min-width: 0;
      width: 100%;
      max-width: 100%;
    }
  }
}

.info-card {
  flex-shrink: 0;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;

  :deep(.glass-card-content) {
    max-width: 100%;
    overflow: hidden;
  }
}

.info-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  margin: 0 0 var(--spacing-3) 0;
  font-size: var(--text-base);
  font-weight: v.$font-semibold;
  color: var(--text-primary);

  .info-icon {
    width: 18px;
    height: 18px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-2) 0;
  border-bottom: 1px solid var(--border-color);

  &:last-child {
    border-bottom: none;
  }
}

.info-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.info-value {
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-primary);

  &.highlight {
    color: var(--text-primary);
    font-weight: v.$font-bold;
  }
}

// Action Buttons
.action-buttons {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  max-width: 100%;

  @include m.respond-below('sm') {
    gap: var(--spacing-2);
  }
}

.codec-selector {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.codec-selector-label {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: v.$font-medium;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.codec-select {
  width: 100%;
  min-height: 44px;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.codec-hint {
  margin: calc(var(--spacing-2) * -1) 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  line-height: 1.4;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  min-height: 44px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;

  .action-icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
    flex-shrink: 0;
  }

  &:hover:not(:disabled) {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
  }

  &.danger:hover:not(:disabled) {
    background: var(--danger-color);
    border-color: var(--danger-color);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}
</style>
