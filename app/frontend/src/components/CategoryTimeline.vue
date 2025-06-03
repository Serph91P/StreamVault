<template>
  <div class="category-timeline" v-if="categoryEvents.length > 0">
    <div class="timeline-header">
      <h4>Category History</h4>
      <span class="category-count">{{ categoryEvents.length }} changes</span>
    </div>
    
    <div class="timeline-container">
      <div class="timeline-line"></div>
      
      <div 
        v-for="(event, index) in categoryEvents" 
        :key="event.id"
        class="timeline-event"
        :class="{ 'first': index === 0, 'last': index === categoryEvents.length - 1 }"
      >
        <div class="timeline-marker">
          <div class="marker-dot"></div>
        </div>
        
        <div class="timeline-content">
          <div class="event-header">
            <div class="category-info">
              <img 
                :src="getCategoryImage(event.category_name)" 
                :alt="event.category_name || 'Unknown Category'"
                class="category-icon"
              />
              <span class="category-name">{{ event.category_name || 'Unknown Category' }}</span>
            </div>
            <span class="event-time">{{ formatTime(event.timestamp) }}</span>
          </div>
          
          <div class="event-details" v-if="event.title">
            <span class="event-title">{{ event.title }}</span>
          </div>
          
          <div class="duration-info" v-if="index < categoryEvents.length - 1">
            <span class="duration">
              Duration: {{ calculateDuration(event.timestamp, getNextTimestamp(index)) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="no-category-history">
    <p>No category changes recorded for this stream</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StreamEvent } from '@/types/streams'

interface Props {
  events: StreamEvent[]
  streamStarted?: string | null
  streamEnded?: string | null
}

const props = defineProps<Props>()

// Filter events to only show category changes
const categoryEvents = computed(() => {
  return props.events
    .filter(event => event.category_name && (event.event_type === 'channel.update' || event.event_type === 'stream.online'))
    .sort((a, b) => new Date(a.timestamp || '').getTime() - new Date(b.timestamp || '').getTime())
})

const getCategoryImage = (categoryName: string | null): string => {
  if (!categoryName) return '/images/default-category.png'
  
  // Simple hash function to generate consistent colors
  let hash = 0
  for (let i = 0; i < categoryName.length; i++) {
    hash = categoryName.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  const hue = Math.abs(hash % 360)
  
  // Generate a placeholder image URL or use a generic game icon
  return `data:image/svg+xml;base64,${btoa(`
    <svg width="40" height="40" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" fill="hsl(${hue}, 70%, 50%)" rx="4"/>
      <text x="20" y="25" text-anchor="middle" fill="white" font-family="Arial" font-size="12" font-weight="bold">
        ${categoryName.substring(0, 2).toUpperCase()}
      </text>
    </svg>
  `)}`
}

const formatTime = (timestamp: string | null): string => {
  if (!timestamp) return 'Unknown time'
  
  const date = new Date(timestamp)
  return date.toLocaleTimeString(undefined, { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

const getNextTimestamp = (currentIndex: number): string | null => {
  if (currentIndex < categoryEvents.value.length - 1) {
    return categoryEvents.value[currentIndex + 1].timestamp
  }
  // If this is the last category change, use stream end time or current time
  return props.streamEnded || new Date().toISOString()
}

const calculateDuration = (startTime: string | null, endTime: string | null): string => {
  if (!startTime || !endTime) return 'Unknown'
  
  const start = new Date(startTime)
  const end = new Date(endTime)
  const diff = end.getTime() - start.getTime()
  
  if (diff < 0) return 'Unknown'
  
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((diff % (1000 * 60)) / 1000)
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`
  } else if (minutes > 0) {
    return `${minutes}m ${seconds}s`
  } else {
    return `${seconds}s`
  }
}
</script>

<style scoped>
.category-timeline {
  background: var(--background-card, #1f1f23);
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  border: 1px solid var(--border-color, #333);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color, #333);
}

.timeline-header h4 {
  margin: 0;
  color: var(--text-primary, #ffffff);
  font-size: 16px;
  font-weight: 600;
}

.category-count {
  background: var(--accent-color, #9146ff);
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.timeline-container {
  position: relative;
  padding-left: 24px;
}

.timeline-line {
  position: absolute;
  left: 8px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: linear-gradient(to bottom, var(--accent-color, #9146ff), var(--accent-color-light, #b876ff));
  border-radius: 1px;
}

.timeline-event {
  position: relative;
  margin-bottom: 16px;
  min-height: 60px;
}

.timeline-event.last {
  margin-bottom: 0;
}

.timeline-marker {
  position: absolute;
  left: -20px;
  top: 8px;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.marker-dot {
  width: 12px;
  height: 12px;
  background: var(--accent-color, #9146ff);
  border-radius: 50%;
  border: 2px solid var(--background-card, #1f1f23);
  box-shadow: 0 0 0 2px var(--accent-color, #9146ff);
}

.timeline-content {
  background: var(--background-secondary, #2a2a2e);
  border-radius: 6px;
  padding: 12px;
  border-left: 3px solid var(--accent-color, #9146ff);
  transition: all 0.2s ease;
}

.timeline-content:hover {
  background: var(--background-hover, #353539);
  transform: translateX(2px);
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.category-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-icon {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  object-fit: cover;
}

.category-name {
  font-weight: 600;
  color: var(--text-primary, #ffffff);
  font-size: 14px;
}

.event-time {
  font-size: 12px;
  color: var(--text-secondary, #b3b3b3);
  font-family: monospace;
}

.event-details {
  margin-bottom: 6px;
}

.event-title {
  font-size: 13px;
  color: var(--text-secondary, #b3b3b3);
  font-style: italic;
}

.duration-info {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--border-color, #333);
}

.duration {
  font-size: 11px;
  color: var(--text-tertiary, #888);
  font-weight: 500;
}

.no-category-history {
  background: var(--background-card, #1f1f23);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  border: 1px solid var(--border-color, #333);
  margin: 12px 0;
}

.no-category-history p {
  margin: 0;
  color: var(--text-secondary, #b3b3b3);
  font-style: italic;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .timeline-container {
    padding-left: 20px;
  }
  
  .timeline-marker {
    left: -16px;
  }
  
  .marker-dot {
    width: 10px;
    height: 10px;
  }
  
  .category-info {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .event-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .timeline-content {
    padding: 10px;
  }
}
</style>
