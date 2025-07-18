<template>
    <div class="video-player-view">
        <!-- Player Header -->
        <div class="player-header">
            <button @click="goBack" class="back-btn">
                ← Back
            </button>
            <div class="stream-info">
                <h1>{{ streamTitle }}</h1>
                <p v-if="streamerName">{{ streamerName }}</p>
            </div>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="loading-container">
            <div class="spinner"></div>
            <p>Loading video player...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="error-container">
            <div class="error-icon">⚠️</div>
            <p class="error-message">{{ error }}</p>
            <button @click="retryLoad" class="btn btn-primary">🔄 Retry</button>
        </div>

        <!-- No Video State -->
        <div v-else-if="!chapterData?.video_url" class="no-video-container">
            <div class="no-video-icon">🎬</div>
            <h3>No video file available</h3>
            <p>This stream doesn't have a video file or it's still being processed.</p>
            <button @click="retryLoad" class="btn btn-secondary">🔄 Refresh</button>
        </div>

        <!-- Video Player -->
        <VideoPlayer v-else :video-src="chapterData.video_url" :chapters="chapterData.chapters"
            :stream-title="chapterData.stream_title" :stream-id="parseInt(streamId)" class="video-player-container"
            @chapter-change="onChapterChange" @video-ready="onVideoReady" @time-update="onTimeUpdate" />
    </div>
</template>

<script setup lang="ts">
// @ts-ignore
import { ref, onMounted, computed } from 'vue'
// @ts-ignore
import { useRoute, useRouter } from 'vue-router'
// @ts-ignore
import VideoPlayer from '@/components/VideoPlayer.vue'
import { videoApi } from '@/services/api'

interface APIChapter {
    id: number
    title: string
    start_time: number
    end_time: number
}

interface ChapterData {
    chapters: Array<{
        start_time: string
        title: string
        type: string
    }>
    stream_id: number
    stream_title: string
    duration?: number
    video_url: string
    video_file: string
    metadata: {
        has_vtt: boolean
        has_srt: boolean
        has_ffmpeg: boolean
    }
}

const route = useRoute()
const router = useRouter()

const streamerId = computed(() => route.params.streamerId as string)
const streamId = computed(() => route.params.streamId as string)
const streamTitle = computed(() => (route.query.title as string) || `Stream ${streamId.value}`)
const streamerName = computed(() => route.query.streamerName as string)

const chapterData = ref<ChapterData | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

const loadChapterData = async () => {
    try {
        isLoading.value = true
        error.value = null

        // Load video chapters using the new API
        const chapters: any[] = await videoApi.getVideoChapters(parseInt(streamId.value))

        // Create chapter data structure compatible with the video player
        chapterData.value = {
            chapters: chapters.map((chapter: any) => ({
                start_time: chapter.start_time.toString(),
                title: chapter.title,
                type: 'chapter'
            })),
            stream_id: parseInt(streamId.value),
            stream_title: streamTitle.value,
            duration: chapters.length > 0 ? chapters[chapters.length - 1].end_time : 0,
            video_url: videoApi.getVideoStreamUrl(parseInt(streamId.value)),
            video_file: `stream_${streamId.value}.mp4`,
            metadata: {
                has_vtt: false,
                has_srt: false,
                has_ffmpeg: true
            }
        }
    } catch (err: any) {
        console.error('Error loading chapter data:', err)
        error.value = err instanceof Error ? err.message : 'Failed to load video data'
    } finally {
        isLoading.value = false
    }
}

const retryLoad = () => {
    loadChapterData()
}

const goBack = () => {
    router.back()
}

// Video player event handlers
const onChapterChange = (chapter: any, index: number) => {
    console.log('Chapter changed:', chapter.title, 'at index:', index)
}

const onVideoReady = (duration: number) => {
    console.log('Video ready, duration:', duration)
}

const onTimeUpdate = (currentTime: number) => {
    // Update progress or other time-based features
}

onMounted(() => {
    loadChapterData()
})
</script>

<style scoped>
.video-player-view {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    background: var(--background-primary);
}

.player-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 20px;
    background: var(--background-card);
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    z-index: 100;
}

.back-btn {
    background: var(--background-darker);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    padding: 10px 16px;
    border-radius: var(--border-radius);
    cursor: pointer;
    transition: all 0.2s;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
}

.back-btn:hover {
    background: var(--background-dark);
    border-color: var(--primary-color);
    color: var(--primary-color);
    transform: translateY(-1px);
}

.stream-info {
    flex: 1;
    min-width: 0;
}

.stream-info h1 {
    margin: 0;
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.stream-info p {
    margin: 4px 0 0 0;
    color: var(--text-secondary);
    font-size: 0.9rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.loading-container,
.error-container,
.no-video-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    text-align: center;
    padding: 40px 20px;
    min-height: 400px;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border-color);
    border-top: 3px solid var(--primary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
}

@keyframes spin {
    0% {
        transform: rotate(0deg);
    }

    100% {
        transform: rotate(360deg);
    }
}

.error-icon,
.no-video-icon {
    font-size: 3rem;
    margin-bottom: 16px;
}

.error-container h3,
.no-video-container h3 {
    margin: 0 0 8px 0;
    color: var(--text-primary);
    font-size: 1.2rem;
}

.error-container p,
.no-video-container p {
    margin: 0 0 20px 0;
    color: var(--text-secondary);
    max-width: 400px;
    line-height: 1.5;
}

.error-message {
    color: var(--danger-color);
    font-weight: 500;
}

.btn {
    background: var(--primary-color);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: var(--border-radius);
    cursor: pointer;
    font-size: 1rem;
    font-weight: 500;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.btn:hover {
    background: var(--primary-color-hover);
    transform: translateY(-1px);
}

.btn.btn-primary {
    background: var(--primary-color);
}

.btn.btn-primary:hover {
    background: var(--primary-color-hover);
}

.btn.btn-secondary {
    background: var(--background-darker);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
}

.btn.btn-secondary:hover {
    background: var(--background-dark);
    border-color: var(--primary-color);
    color: var(--primary-color);
}

.video-player-container {
    flex: 1;
    display: flex;
    flex-direction: column;
}

/* Mobile Responsive */
@media (max-width: 768px) {
    .player-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 16px;
    }

    .back-btn {
        align-self: flex-start;
    }

    .stream-info {
        width: 100%;
    }

    .stream-info h1 {
        font-size: 1.2rem;
        white-space: normal;
        overflow: visible;
        text-overflow: unset;
        line-height: 1.3;
    }

    .stream-info p {
        white-space: normal;
        overflow: visible;
        text-overflow: unset;
    }

    .loading-container,
    .error-container,
    .no-video-container {
        padding: 20px 16px;
        min-height: 300px;
    }

    .error-icon,
    .no-video-icon {
        font-size: 2.5rem;
    }

    .btn {
        padding: 14px 24px;
        width: 100%;
        max-width: 200px;
        justify-content: center;
    }
}

/* Small mobile screens */
@media (max-width: 480px) {
    .player-header {
        padding: 10px 12px;
    }

    .stream-info h1 {
        font-size: 1.1rem;
    }

    .stream-info p {
        font-size: 0.85rem;
    }

    .loading-container,
    .error-container,
    .no-video-container {
        padding: 16px 12px;
    }

    .error-container h3,
    .no-video-container h3 {
        font-size: 1.1rem;
    }

    .error-container p,
    .no-video-container p {
        font-size: 0.9rem;
    }
}

/* Landscape mobile */
@media (max-width: 768px) and (orientation: landscape) {
    .player-header {
        flex-direction: row;
        align-items: center;
        padding: 8px 16px;
    }

    .stream-info h1 {
        font-size: 1.1rem;
    }

    .stream-info p {
        font-size: 0.8rem;
    }

    .loading-container,
    .error-container,
    .no-video-container {
        min-height: 200px;
        padding: 20px 16px;
    }
}
</style>
