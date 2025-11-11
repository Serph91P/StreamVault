<template>
  <div class="streamers-view">
    <!-- Header -->
    <div class="view-header">
      <div class="header-content">
        <h1 class="page-title">
          <svg class="icon-title">
            <use href="#icon-users" />
          </svg>
          Streamers
        </h1>
        <p class="page-subtitle">
          Manage your tracked streamers •
          <span v-if="!isLoading" class="status-text">
            {{ liveStreamers.length }} live now
          </span>
          <span v-if="autoRefresh" class="auto-refresh-indicator">
            <span class="pulse-dot"></span>
            Auto-refresh
          </span>
        </p>
      </div>

      <div class="header-actions">
        <button
          @click="toggleAutoRefresh"
          class="btn-action"
          :class="autoRefresh ? 'btn-primary' : 'btn-secondary'"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-refresh-cw" />
          </svg>
          Auto {{ autoRefresh ? 'ON' : 'OFF' }}
        </button>
        <router-link to="/add-streamer" class="btn-action btn-primary" v-ripple>
          <svg class="icon">
            <use href="#icon-plus" />
          </svg>
          Add Streamer
        </router-link>
      </div>
    </div>

    <!-- Controls Bar -->
    <div class="controls-bar">
      <!-- Search -->
      <div class="search-box">
        <svg class="search-icon">
          <use href="#icon-search" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search streamers..."
          class="search-input"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="clear-btn"
        >
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
        </button>
      </div>

      <!-- Filter Tabs -->
      <div class="filter-tabs">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          @click="activeFilter = tab.value"
          :class="{ active: activeFilter === tab.value }"
          class="filter-tab"
          v-ripple
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined" class="tab-badge">
            {{ tab.count }}
          </span>
        </button>
      </div>

      <!-- View Toggle -->
      <div class="view-toggle">
        <button
          @click="viewMode = 'grid'"
          :class="{ active: viewMode === 'grid' }"
          class="toggle-btn"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-grid" />
          </svg>
        </button>
        <button
          @click="viewMode = 'list'"
          :class="{ active: viewMode === 'list' }"
          class="toggle-btn"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-list" />
          </svg>
        </button>
      </div>

      <!-- Sort -->
      <select v-model="sortBy" class="sort-select">
        <option value="name">Name A-Z</option>
        <option value="name-desc">Name Z-A</option>
        <option value="live-first">Live First</option>
        <option value="recently-added">Recently Added</option>
        <option value="most-videos">Most Videos</option>
      </select>
    </div>

    <!-- Last Update Info -->
    <div v-if="lastUpdateTime" class="update-info">
      Last updated: {{ formatLastUpdate(lastUpdateTime) }}
      <button @click="handleRefresh" class="refresh-btn" v-ripple>
        <svg class="icon" :class="{ spinning: isRefreshing }">
          <use href="#icon-refresh-cw" />
        </svg>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="streamers-container" :class="`view-${viewMode}`">
      <LoadingSkeleton
        v-for="i in 6"
        :key="i"
        type="streamer"
      />
    </div>

    <!-- Empty State -->
    <EmptyState
      v-else-if="filteredAndSortedStreamers.length === 0 && !searchQuery"
      title="No Streamers Yet"
      description="Add your first streamer to start tracking and recording their content."
      icon="users"
      action-label="Add Streamer"
      action-icon="plus"
      @action="$router.push('/add-streamer')"
    />

    <!-- No Search Results -->
    <EmptyState
      v-else-if="filteredAndSortedStreamers.length === 0 && searchQuery"
      title="No Results Found"
      :description="`No streamers match '${searchQuery}'`"
      icon="search"
      action-label="Clear Search"
      @action="searchQuery = ''"
    />

    <!-- Streamers Grid/List -->
    <div v-else class="streamers-container" :class="`view-${viewMode}`">
      <div
        v-for="(streamer, index) in filteredAndSortedStreamers"
        :key="streamer.id"
        class="streamer-wrapper"
        :style="{ animationDelay: `${index * 50}ms` }"
      >
        <StreamerCard
          :streamer="streamer"
          :view-mode="viewMode"
          @click="navigateToDetail(streamer)"
          @watch="handleWatch"
          @force-record="handleForceRecord"
          @delete="handleDelete"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { streamersApi } from '@/services/api'
import { useWebSocket } from '@/composables/useWebSocket'
import { useForceRecording } from '@/composables/useForceRecording'  // NEW: Import composable
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StreamerCard from '@/components/cards/StreamerCard.vue'

const router = useRouter()

// WebSocket for real-time updates
const { messages } = useWebSocket()

// Force recording composable
const { forceStartRecording } = useForceRecording()  // NEW: Use composable

// State
const isLoading = ref(true)
const isRefreshing = ref(false)
const streamers = ref<any[]>([])
const searchQuery = ref('')
const viewMode = ref<'grid' | 'list'>('grid')
const sortBy = ref('live-first')
const activeFilter = ref('all')
const autoRefresh = ref(true)
const lastUpdateTime = ref<Date | null>(null)

// Auto-refresh interval
let refreshInterval: number | null = null
const REFRESH_INTERVAL = 30000 // 30 seconds

// Filter tabs with counts
const filterTabs = computed(() => [
  {
    label: 'All',
    value: 'all',
    count: streamers.value.length
  },
  {
    label: 'Live',
    value: 'live',
    count: liveStreamers.value.length
  },
  {
    label: 'Offline',
    value: 'offline',
    count: streamers.value.length - liveStreamers.value.length
  }
])

// Live streamers
const liveStreamers = computed(() => {
  return streamers.value.filter(s => s.is_live)
})

// Filtered and sorted streamers
const filteredAndSortedStreamers = computed(() => {
  let filtered = [...streamers.value]

  // Search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(s =>
      s.name?.toLowerCase().includes(query) ||
      s.display_name?.toLowerCase().includes(query)
    )
  }

  // Status filter
  switch (activeFilter.value) {
    case 'live':
      filtered = filtered.filter(s => s.is_live)
      break
    case 'offline':
      filtered = filtered.filter(s => !s.is_live)
      break
    // 'all' - no filtering
  }

  // Sorting
  const sorted = [...filtered]
  switch (sortBy.value) {
    case 'name':
      sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
      break
    case 'name-desc':
      sorted.sort((a, b) => (b.name || '').localeCompare(a.name || ''))
      break
    case 'live-first':
      sorted.sort((a, b) => {
        if (a.is_live && !b.is_live) return -1
        if (!a.is_live && b.is_live) return 1
        return (a.name || '').localeCompare(b.name || '')
      })
      break
    case 'recently-added':
      sorted.sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime()
        const dateB = new Date(b.created_at || 0).getTime()
        return dateB - dateA
      })
      break
    case 'most-videos':
      sorted.sort((a, b) => (b.video_count || 0) - (a.video_count || 0))
      break
  }

  return sorted
})

// Fetch streamers
async function fetchStreamers() {
  try {
    const response = await streamersApi.getAll()
    // Backend returns {streamers: [...]} format
    streamers.value = response.streamers || []
    lastUpdateTime.value = new Date()
  } catch (error) {
    console.error('Failed to fetch streamers:', error)
    streamers.value = []
  }
}

// Initial load
async function loadStreamers() {
  isLoading.value = true
  await fetchStreamers()
  isLoading.value = false
}

// Refresh
async function handleRefresh() {
  isRefreshing.value = true
  await fetchStreamers()
  isRefreshing.value = false
}

// Auto-refresh setup
function startAutoRefresh() {
  if (refreshInterval !== null) return
  refreshInterval = window.setInterval(() => {
    if (autoRefresh.value && document.visibilityState === 'visible') {
      fetchStreamers()
    }
  }, REFRESH_INTERVAL)
}

function stopAutoRefresh() {
  if (refreshInterval !== null) {
    window.clearInterval(refreshInterval)
    refreshInterval = null
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    startAutoRefresh()
    handleRefresh()
  } else {
    stopAutoRefresh()
  }
}

// Format last update time
function formatLastUpdate(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`

  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`

  const diffHour = Math.floor(diffMin / 60)
  return `${diffHour}h ago`
}

// Navigate to detail
function navigateToDetail(streamer: any) {
  router.push({
    name: 'streamer-detail',
    params: { id: streamer.id },
    query: { name: streamer.name }
  })
}

// Handle force record action
async function handleForceRecord(streamer: any) {
  await forceStartRecording(streamer.id, async () => {
    // Refresh streamers after successful force record
    await fetchStreamers()
  })
}

// Handle watch live action
function handleWatch(streamer: any) {
  // Open Twitch stream in new tab
  window.open(`https://twitch.tv/${streamer.username}`, '_blank')
}

// Handle delete streamer action
async function handleDelete(streamer: any) {
  const displayName = streamer.display_name || streamer.username || 'this streamer'
  if (!confirm(`Delete ${displayName}? This will also delete all their recordings.`)) {
    return
  }

  try {
    await streamersApi.delete(streamer.id)
    streamers.value = streamers.value.filter(s => s.id !== streamer.id)
  } catch (error) {
    console.error('Failed to delete streamer:', error)
    alert('Failed to delete streamer. Please try again.')
  }
}

// WebSocket: Real-time updates for streamer status
watch(messages, (newMessages) => {
  if (!newMessages || newMessages.length === 0) return
  
  // Process latest message
  const latestMessage = newMessages[newMessages.length - 1]
  
  // Handle stream status changes
  if (latestMessage.type === 'stream.online' || 
      latestMessage.type === 'stream.offline' ||
      latestMessage.type === 'channel.update' ||
      latestMessage.type === 'stream.update') {
    
    const username = latestMessage.data?.username || latestMessage.data?.streamer_name
    if (!username) return
    
    // Find streamer in list
    const streamerIndex = streamers.value.findIndex(
      s => s.username?.toLowerCase() === username.toLowerCase() ||
           s.name?.toLowerCase() === username.toLowerCase()
    )
    
    if (streamerIndex === -1) return
    
    // Update streamer data based on message type
    const streamer = { ...streamers.value[streamerIndex] }
    
    if (latestMessage.type === 'stream.online') {
      streamer.is_live = true
      streamer.title = latestMessage.data?.title
      streamer.category_name = latestMessage.data?.category_name
      console.log(`[WebSocket] ${username} went LIVE: ${streamer.title}`)
    } else if (latestMessage.type === 'stream.offline') {
      streamer.is_live = false
      streamer.title = null
      streamer.category_name = null
      console.log(`[WebSocket] ${username} went OFFLINE`)
    } else if (latestMessage.type === 'channel.update' || latestMessage.type === 'stream.update') {
      // Update title and category in real-time
      if (latestMessage.data?.title) {
        streamer.title = latestMessage.data.title
      }
      if (latestMessage.data?.category_name) {
        streamer.category_name = latestMessage.data.category_name
      }
      console.log(`[WebSocket] ${username} updated: ${streamer.title} | ${streamer.category_name}`)
    }
    
    // Update the streamer in array (trigger reactivity)
    streamers.value = [
      ...streamers.value.slice(0, streamerIndex),
      streamer,
      ...streamers.value.slice(streamerIndex + 1)
    ]
  }
}, { deep: true })

// Lifecycle
onMounted(async () => {
  await loadStreamers()
  if (autoRefresh.value) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
.streamers-view {
  padding: var(--spacing-6) var(--spacing-4);
  max-width: 1600px;
  margin: 0 auto;
  min-height: 100vh;
}

// Header
.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-6);
  gap: var(--spacing-4);
  flex-wrap: wrap;
}

.header-content {
  flex: 1;
  min-width: 250px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  font-size: var(--text-3xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-2) 0;

  .icon-title {
    width: 32px;
    height: 32px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  flex-wrap: wrap;
}

.status-text {
  color: var(--danger-color);
  font-weight: v.$font-semibold;
}

.auto-refresh-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-1) var(--spacing-2);
  background: rgba(var(--success-500-rgb), 0.1);
  color: var(--success-color);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  font-weight: v.$font-medium;
}

.pulse-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: var(--success-color);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
}

.header-actions {
  display: flex;
  gap: var(--spacing-3);
  flex-wrap: wrap;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  border: none;
  cursor: pointer;
  text-decoration: none;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }

  &.btn-primary {
    background: var(--primary-color);
    color: white;

    &:hover {
      background: var(--primary-600);  /* Darker green when ON */
      box-shadow: var(--shadow-md);
    }
  }

  &.btn-secondary {
    background: var(--background-card);
    color: var(--text-primary);
    border: 1px solid var(--border-color);

    &:hover {
      background: var(--primary-color);  /* Green background when hovering OFF state */
      border-color: var(--primary-color);
      color: white;  /* White text when hovering */
    }
  }
}

// Controls Bar
.controls-bar {
  display: flex;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
  flex-wrap: wrap;
  align-items: center;
}

.search-box {
  position: relative;
  flex: 1;
  min-width: 280px;

  .search-icon {
    position: absolute;
    left: var(--spacing-3);
    top: 50%;
    transform: translateY(-50%);
    width: 20px;
    height: 20px;
    stroke: var(--text-secondary);
    fill: none;
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    padding: var(--spacing-3) var(--spacing-10) var(--spacing-3) var(--spacing-10);
    background: var(--background-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    color: var(--text-primary);
    font-size: var(--text-sm);
    transition: all v.$duration-200 v.$ease-out;

    &:focus {
      outline: none;
      border-color: var(--primary-color);
      box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
    }

    &::placeholder {
      color: var(--text-tertiary);
    }
  }

  .clear-btn {
    position: absolute;
    right: var(--spacing-2);
    top: 50%;
    transform: translateY(-50%);
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all v.$duration-200 v.$ease-out;

    .icon {
      width: 16px;
      height: 16px;
      stroke: var(--text-secondary);
      fill: none;
    }

    &:hover {
      background: rgba(var(--danger-500-rgb), 0.1);

      .icon {
        stroke: var(--danger-color);
      }
    }
  }
}

.filter-tabs {
  display: flex;
  gap: var(--spacing-1);
  background: var(--background-card);
  border-radius: var(--radius-lg);
  padding: var(--spacing-1);
  border: 1px solid var(--border-color);
}

.filter-tab {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &.active {
    background: var(--primary-color);
    color: white;

    .tab-badge {
      background: rgba(255, 255, 255, 0.2);
      color: white;
    }
  }

  &:hover:not(.active) {
    background: rgba(var(--primary-500-rgb), 0.1);
    color: var(--primary-color);
  }

  .tab-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 var(--spacing-1);
    background: var(--background-darker);
    color: var(--text-primary);
    font-size: var(--text-xs);
    font-weight: v.$font-bold;
    border-radius: var(--radius-full);
  }
}

.view-toggle {
  display: flex;
  gap: var(--spacing-1);
  background: var(--background-card);
  border-radius: var(--radius-lg);
  padding: var(--spacing-1);
  border: 1px solid var(--border-color);
}

.toggle-btn {
  padding: var(--spacing-2);
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: var(--text-secondary);
    fill: none;
  }

  &.active {
    background: var(--primary-color);

    .icon {
      stroke: white;
    }
  }

  &:hover:not(.active) {
    background: rgba(var(--primary-500-rgb), 0.1);
  }
}

.sort-select {
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    border-color: var(--primary-color);
  }

  &:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

// Update Info
.update-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-4);
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 16px;
    height: 16px;
    stroke: var(--text-secondary);
    fill: none;
    transition: transform v.$duration-200 v.$ease-out;

    &.spinning {
      animation: spin 1s linear infinite;
    }
  }

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);

    .icon {
      stroke: var(--primary-color);
    }
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

// Streamers Container
.streamers-container {
  &.view-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));  /* INCREASED from 320px */
    gap: var(--spacing-5);
    align-items: start;  /* CRITICAL: Prevent cards from stretching */
  }

  &.view-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }
}

.streamer-wrapper {
  animation: fade-in-up v.$duration-500 v.$ease-out backwards;
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@include m.respond-below('lg') {  // < 1024px
  .controls-bar {
    flex-wrap: wrap;
  }

  .search-box {
    order: -1;
    width: 100%;
    flex-basis: 100%;
    min-width: unset;
  }

  .filter-tabs {
    flex: 1;
  }
}

@include m.respond-below('sm') {  // < 640px
  .streamers-view {
    padding: var(--spacing-4) var(--spacing-3);
  }

  .page-title {
    font-size: var(--text-2xl);
  }

  .header-actions {
    width: 100%;

    .btn-action {
      flex: 1;
      justify-content: center;
      min-height: 44px;  // Touch-friendly
    }
  }
  
  .controls-bar {
    gap: var(--spacing-2);
  }

  .search-box {
    .search-input {
      min-height: 44px;  // Touch-friendly
      font-size: 16px;  // Prevent iOS zoom
      padding: var(--spacing-3) var(--spacing-10);
    }
    
    .clear-btn {
      width: 32px;  // Larger touch target
      height: 32px;
      
      .icon {
        width: 18px;
        height: 18px;
      }
    }
  }

  .filter-tabs {
    width: 100%;
    justify-content: stretch;
    flex: none;  // Don't shrink

    .filter-tab {
      flex: 1;
      justify-content: center;
      min-height: 40px;  // Touch-friendly
      padding: var(--spacing-2) var(--spacing-2);
      font-size: var(--text-xs);
      
      .tab-badge {
        font-size: 10px;
        min-width: 18px;
        height: 18px;
      }
    }
  }
  
  .view-toggle {
    flex: none;  // Fixed width
    
    .toggle-btn {
      min-width: 44px;  // Touch-friendly
      min-height: 44px;
      padding: var(--spacing-2);
      
      .icon {
        width: 22px;
        height: 22px;
      }
    }
  }
  
  .sort-select {
    flex: 1;  // Fill remaining space
    min-height: 44px;  // Touch-friendly
    font-size: 16px;  // Prevent iOS zoom
    padding: var(--spacing-3);
  }

  .streamers-container.view-grid {
    grid-template-columns: 1fr;
  }
}
</style>
