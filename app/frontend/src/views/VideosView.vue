<template>
    <div class="videos-view">
        <div class="view-header">
            <h1>📹 Videos</h1>
            <p>Browse and watch all recorded streams</p>
        </div>

        <!-- Filter und Suche -->
        <div class="filters">
            <div class="search-box">
                <input v-model="searchQuery" type="text" placeholder="Search videos..." class="search-input">
                <button @click="searchVideos" class="search-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"></circle>
                        <path d="m21 21-4.35-4.35"></path>
                    </svg>
                </button>
            </div>

            <div class="filter-buttons">
                <button v-for="filter in filters" :key="filter.value" @click="activeFilter = filter.value"
                    :class="['filter-btn', { active: activeFilter === filter.value }]">
                    {{ filter.label }}
                </button>
            </div>

            <div class="category-filter" v-if="availableCategories.length > 1">
                <h4>Filter by Category:</h4>
                <div class="category-buttons">
                    <button v-for="category in availableCategories" :key="category.value"
                        @click="activeCategoryFilter = category.value"
                        :class="['category-btn', { active: activeCategoryFilter === category.value }]">
                        {{ category.label }}
                    </button>
                </div>
            </div>
        </div>

        <!-- Loading State -->
        <div v-if="loading" class="loading-container">
            <div class="loading-spinner"></div>
            <p>Loading videos...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="error-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <h3>Error loading videos</h3>
            <p>{{ error }}</p>
            <button @click="loadVideos" class="retry-btn">Try Again</button>
        </div>

        <!-- Videos Grid -->
        <div v-else-if="filteredVideos.length > 0" class="videos-grid">
            <div v-for="video in filteredVideos" :key="video.id" class="video-card" @click="openVideoModal(video)">
                <div class="video-thumbnail">
                    <img v-if="video.thumbnail_url" :src="video.thumbnail_url" :alt="video.title"
                        class="thumbnail-image" @error="handleThumbnailError">
                    <div v-else class="thumbnail-placeholder">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2">
                            <polygon points="23 7 16 12 23 17 23 7"></polygon>
                            <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
                        </svg>
                    </div>

                    <div class="video-duration" v-if="video.duration">
                        {{ formatDuration(video.duration) }}
                    </div>

                    <div class="video-overlay">
                        <svg class="play-icon" width="24" height="24" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2">
                            <polygon points="5 3 19 12 5 21 5 3"></polygon>
                        </svg>
                    </div>
                </div>

                <div class="video-info">
                    <h3 class="video-title">{{ video.title }}</h3>
                    <p class="video-streamer">{{ video.streamer_name }}</p>
                    <p v-if="video.category_name" class="video-category">🎮 {{ video.category_name }}</p>
                    <div class="video-meta">
                        <span class="video-date">{{ formatDate(video.created_at) }}</span>
                        <span class="video-size" v-if="video.file_size">{{ formatFileSize(video.file_size) }}</span>
                    </div>
                </div>
            </div>
        </div> <!-- Empty State -->
        <div v-else-if="!loading && !error" class="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <polygon points="23 7 16 12 23 17 23 7"></polygon>
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
            </svg>
            <h3>No videos found</h3>
            <p v-if="searchQuery">No videos match your search for "{{ searchQuery }}"</p>
            <p v-else>No videos have been recorded yet.</p>
        </div>

        <!-- Video Modal -->
        <VideoModal v-if="selectedVideo" :video="selectedVideo" @close="closeVideoModal" />
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VideoModal from '@/components/VideoModal.vue'
import { videoApi } from '@/services/api'

const loading = ref(true)
const searchQuery = ref('')
const activeFilter = ref('all')
const activeCategoryFilter = ref('all')
const selectedVideo = ref(null)
const videos = ref([])
const error = ref(null)

const filters = [
    { label: 'All', value: 'all' },
    { label: 'Today', value: 'today' },
    { label: 'This Week', value: 'week' },
    { label: 'This Month', value: 'month' }
]

// Get unique categories from videos
const availableCategories = computed(() => {
    const categories = videos.value
        .map(video => video.category_name)
        .filter(category => category && category.trim() !== '')
        .filter((category, index, array) => array.indexOf(category) === index)
        .sort()

    return [
        { label: 'All Categories', value: 'all' },
        ...categories.map(category => ({ label: category, value: category }))
    ]
})

const filteredVideos = computed(() => {
    let filtered = videos.value

    // Filter by search query
    if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase()
        filtered = filtered.filter(video =>
            (video.title || '').toLowerCase().includes(query) ||
            (video.streamer_name || '').toLowerCase().includes(query)
        )
    }

    // Filter by category
    if (activeCategoryFilter.value !== 'all') {
        filtered = filtered.filter(video =>
            video.category_name === activeCategoryFilter.value
        )
    }

    // Filter by date
    if (activeFilter.value !== 'all') {
        const now = new Date()
        const filterDate = new Date()

        switch (activeFilter.value) {
            case 'today':
                filterDate.setHours(0, 0, 0, 0)
                break
            case 'week':
                filterDate.setDate(now.getDate() - 7)
                break
            case 'month':
                filterDate.setMonth(now.getMonth() - 1)
                break
        }

        filtered = filtered.filter(video => {
            if (!video.created_at) return false
            try {
                const videoDate = new Date(video.created_at)
                return videoDate >= filterDate
            } catch (e) {
                console.warn('Invalid date format:', video.created_at)
                return false
            }
        })
    }

    // Sort by date (newest first)
    const result = filtered.sort((a, b) => {
        try {
            const dateA = new Date(a.created_at || 0)
            const dateB = new Date(b.created_at || 0)
            return dateB - dateA
        } catch (e) {
            return 0
        }
    })

    return result
})

const loadVideos = async () => {
    try {
        loading.value = true
        error.value = null
        const response = await videoApi.getAll()
        // API returns array directly, not wrapped in data
        videos.value = Array.isArray(response) ? response : (response.data || [])
        console.log('Loaded videos:', videos.value)
    } catch (err) {
        console.error('Error loading videos:', err)
        error.value = err.response?.data?.detail || err.message || 'Failed to load videos'
        videos.value = []
    } finally {
        loading.value = false
    }
}

const searchVideos = () => {
    // Trigger reactivity by updating computed
    // The computed property will automatically filter
}

const openVideoModal = (video) => {
    selectedVideo.value = video
}

const closeVideoModal = () => {
    selectedVideo.value = null
}

const handleThumbnailError = (event) => {
    event.target.style.display = 'none'
}

const formatDate = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInHours = (now - date) / (1000 * 60 * 60)

    if (diffInHours < 24) {
        return `${Math.floor(diffInHours)} hours ago`
    } else if (diffInHours < 24 * 7) {
        return `${Math.floor(diffInHours / 24)} days ago`
    } else {
        return date.toLocaleDateString('en-US', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        })
    }
}

const formatDuration = (seconds) => {
    if (!seconds) return ''

    // Round to whole seconds to avoid decimal display
    const totalSeconds = Math.round(seconds)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const secs = totalSeconds % 60

    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`
    }
}

const formatFileSize = (bytes) => {
    if (!bytes) return ''

    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
}

onMounted(() => {
    loadVideos()
})
</script>

<style scoped>
.videos-view {
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
}

.view-header {
    text-align: center;
    margin-bottom: 30px;
}

.view-header h1 {
    font-size: 2.5rem;
    margin-bottom: 10px;
    color: var(--text-primary);
}

.view-header p {
    color: var(--text-secondary);
    font-size: 1.1rem;
}

.filters {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-bottom: 30px;
    padding: 20px;
    background: var(--bg-secondary);
    border-radius: 12px;
}

.search-box {
    display: flex;
    gap: 10px;
    max-width: 400px;
    margin: 0 auto;
}

.search-input {
    flex: 1;
    padding: 12px 16px;
    border: 2px solid var(--border-color);
    border-radius: 25px;
    font-size: 16px;
    outline: none;
    transition: border-color 0.3s;
}

.search-input:focus {
    border-color: var(--primary-color);
}

.search-btn {
    padding: 12px 16px;
    background: var(--primary-color);
    color: white;
    border: none;
    border-radius: 25px;
    cursor: pointer;
    transition: background-color 0.3s;
}

.search-btn:hover {
    background: var(--primary-hover);
}

.filter-buttons {
    display: flex;
    gap: 10px;
    justify-content: center;
    flex-wrap: wrap;
}

.filter-btn {
    padding: 8px 20px;
    border: 2px solid var(--border-color);
    background: transparent;
    color: var(--text-primary);
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.3s;
}

.filter-btn:hover,
.filter-btn.active {
    background: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
}

.category-filter {
    margin-top: 15px;
}

.category-filter h4 {
    margin: 0 0 10px 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
    text-align: center;
}

.category-buttons {
    display: flex;
    gap: 8px;
    justify-content: center;
    flex-wrap: wrap;
}

.category-btn {
    padding: 6px 16px;
    border: 2px solid var(--border-color);
    background: transparent;
    color: var(--text-primary);
    border-radius: 15px;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 0.85rem;
}

.category-btn:hover,
.category-btn.active {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
}

.loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
}

.loading-spinner {
    width: 40px;
    height: 40px;
    border: 4px solid var(--border-color);
    border-top: 4px solid var(--primary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 20px;
}

@keyframes spin {
    0% {
        transform: rotate(0deg);
    }

    100% {
        transform: rotate(360deg);
    }
}

.videos-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;
}

.video-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    position: relative;
}

.video-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    border-color: var(--primary-color);
}

.video-card:nth-child(odd) {
    background: var(--bg-secondary);
}

.video-card:nth-child(even) {
    background: var(--bg-tertiary);
}

.video-thumbnail {
    position: relative;
    width: 100%;
    height: 180px;
    overflow: hidden;
}

.thumbnail-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.thumbnail-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--bg-tertiary) 0%, #404040 100%);
    color: var(--text-secondary);
    border: 2px dashed var(--border-color);
}

.video-duration {
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
}

.video-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity 0.3s;
}

.video-card:hover .video-overlay {
    opacity: 1;
}

.play-icon {
    color: white;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5));
}

.video-info {
    padding: 16px;
    background: rgba(255, 255, 255, 0.02);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.video-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--text-primary);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.video-streamer {
    color: var(--primary-color);
    font-weight: 500;
    margin-bottom: 8px;
}

.video-category {
    color: var(--accent-color);
    font-size: 0.85rem;
    margin-bottom: 8px;
    font-weight: 500;
}

.video-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.empty-state {
    text-align: center;
    padding: 80px 20px;
    color: var(--text-secondary);
}

.empty-state svg {
    margin-bottom: 20px;
    opacity: 0.5;
}

.empty-state h3 {
    font-size: 1.5rem;
    margin-bottom: 10px;
    color: var(--text-primary);
}

.error-state {
    text-align: center;
    padding: 80px 20px;
    color: var(--text-secondary);
}

.error-state svg {
    margin-bottom: 20px;
    color: #e74c3c;
}

.error-state h3 {
    font-size: 1.5rem;
    margin-bottom: 10px;
    color: var(--text-primary);
}

.retry-btn {
    padding: 10px 20px;
    background: var(--primary-color);
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    margin-top: 15px;
    transition: background-color 0.3s;
}

.retry-btn:hover {
    background: var(--primary-hover);
}

/* Mobile Responsive */
@media (max-width: 768px) {
    .videos-view {
        padding: 15px;
    }

    .view-header h1 {
        font-size: 2rem;
    }

    .filters {
        padding: 15px;
    }

    .search-box {
        max-width: 100%;
    }

    .videos-grid {
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 15px;
    }

    .video-thumbnail {
        height: 160px;
    }

    .filter-buttons {
        justify-content: flex-start;
        overflow-x: auto;
        padding-bottom: 5px;
    }

    .filter-btn {
        flex-shrink: 0;
    }

    .category-buttons {
        justify-content: flex-start;
        overflow-x: auto;
        padding-bottom: 5px;
    }

    .category-btn {
        flex-shrink: 0;
        font-size: 0.8rem;
        padding: 5px 12px;
    }
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
    :root {
        --bg-primary: #1a1a1a;
        --bg-secondary: #2d2d2d;
        --bg-tertiary: #383838;
        --text-primary: #ffffff;
        --text-secondary: #b0b0b0;
        --border-color: #404040;
        --primary-color: #6f42c1;
        --primary-hover: #5a359a;
        --accent-color: #28a745;
    }
}

/* Light mode support */
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f8f9fa;
    --bg-tertiary: #e9ecef;
    --text-primary: #212529;
    --text-secondary: #6c757d;
    --border-color: #dee2e6;
    --primary-color: #6f42c1;
    --primary-hover: #5a359a;
    --accent-color: #28a745;
}
</style>
