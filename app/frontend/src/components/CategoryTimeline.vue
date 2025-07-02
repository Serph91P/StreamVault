<template>
  <div class="category-timeline" v-if="categoryEvents.length > 0">
    <div class="timeline-header">
      <h4><i class="fas fa-history"></i> Category Timeline</h4>
      <span class="category-count">{{ categoryEvents.length }} {{ categoryEvents.length === 1 ? 'category' : 'categories' }}</span>
    </div>
    
    <!-- Horizontal Timeline -->
    <div class="horizontal-timeline">
      <div class="timeline-track"></div>
      
      <div 
        v-for="(event, index) in categoryEvents" 
        :key="event.id"
        class="timeline-item"
        :style="{ left: getTimelinePosition(event, index) + '%' }"
      >
        <div class="timeline-marker">
          <div class="marker-content">
            <div class="category-icon-wrapper">
              <i :class="getCategoryIcon(event.category_name)" class="category-icon"></i>
            </div>
          </div>
        </div>
        
        <div class="timeline-tooltip">
          <div class="tooltip-header">
            <strong>{{ event.category_name || 'Unknown Category' }}</strong>
          </div>
          <div class="tooltip-time">{{ formatTime(event.timestamp) }}</div>
          <div v-if="event.title" class="tooltip-title">{{ event.title }}</div>
          <div v-if="index < categoryEvents.length - 1" class="tooltip-duration">
            Duration: {{ calculateDuration(event.timestamp, getNextTimestamp(index)) }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- Category List (compact) -->
    <div class="category-list">
      <div 
        v-for="(event, index) in categoryEvents" 
        :key="event.id"
        class="category-item"
      >
        <div class="category-marker">
          <i :class="getCategoryIcon(event.category_name)" class="category-icon"></i>
        </div>
        <div class="category-details">
          <div class="category-name">{{ event.category_name || 'Unknown' }}</div>
          <div class="category-time">{{ formatTime(event.timestamp) }}</div>
          <div v-if="index < categoryEvents.length - 1" class="category-duration">
            {{ calculateDuration(event.timestamp, getNextTimestamp(index)) }}
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="no-category-history">
    <div class="no-data-content">
      <i class="fas fa-info-circle"></i>
      <p>No category changes recorded for this stream</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCategoryImages } from '@/composables/useCategoryImages'
import type { StreamEvent } from '@/types/streams'

interface Props {
  events: StreamEvent[]
  streamStarted?: string | null
  streamEnded?: string | null
}

const props = defineProps<Props>()
const { getCategoryImage } = useCategoryImages()

// Filter events to only show category changes
const categoryEvents = computed(() => {
  return props.events
    .filter(event => event.category_name && (event.event_type === 'channel.update' || event.event_type === 'stream.online'))
    .sort((a, b) => new Date(a.timestamp || '').getTime() - new Date(b.timestamp || '').getTime())
})

const getCategoryIcon = (categoryName: string | null): string => {
  if (!categoryName) return 'fas fa-video';
  
  const imageUrl = getCategoryImage(categoryName);
  
  // If it's an icon (starts with icon:), return the icon class
  if (imageUrl.startsWith('icon:')) {
    return imageUrl.replace('icon:', '');
  }
  
  // For actual images, return a generic gaming icon as fallback for the timeline
  return 'fas fa-gamepad';
}

const getTimelinePosition = (event: any, index: number): number => {
  if (categoryEvents.value.length <= 1) return 50;
  
  // Calculate position based on chronological order
  const totalEvents = categoryEvents.value.length;
  const margin = 5; // 5% margin on each side
  const usableWidth = 100 - (margin * 2);
  
  return margin + (index * (usableWidth / (totalEvents - 1)));
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
  background: #1f1f23;
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0;
  border: 1px solid #333;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #333;
}

.timeline-header h4 {
  margin: 0;
  color: #ffffff;
  font-size: 1.1rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.timeline-header h4 i {
  color: #9146FF;
}

.category-count {
  background: #9146FF;
  color: white;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 0.8rem;
  font-weight: 500;
}

/* Horizontal Timeline */
.horizontal-timeline {
  position: relative;
  height: 80px;
  margin: 20px 0;
  overflow-x: auto;
  overflow-y: visible;
}

.timeline-track {
  position: absolute;
  top: 40px;
  left: 5%;
  right: 5%;
  height: 2px;
  background: linear-gradient(90deg, #9146FF, #6441A5);
  border-radius: 2px;
}

.timeline-item {
  position: absolute;
  top: 20px;
  transform: translateX(-50%);
  cursor: pointer;
}

.timeline-marker {
  position: relative;
  z-index: 2;
}

.marker-content {
  width: 40px;
  height: 40px;
  background: #9146FF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(145, 70, 255, 0.4);
  transition: all 0.3s ease;
}

.timeline-item:hover .marker-content {
  transform: scale(1.1);
  box-shadow: 0 4px 16px rgba(145, 70, 255, 0.6);
}

.category-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.category-icon {
  color: white;
  font-size: 16px;
}

/* Tooltip */
.timeline-tooltip {
  position: absolute;
  top: -120px;
  left: 50%;
  transform: translateX(-50%);
  background: #18181b;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 12px;
  min-width: 180px;
  opacity: 0;
  visibility: hidden;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  z-index: 10;
}

.timeline-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #333;
}

.timeline-item:hover .timeline-tooltip {
  opacity: 1;
  visibility: visible;
}

.tooltip-header {
  color: #9146FF;
  font-weight: 600;
  margin-bottom: 4px;
}

.tooltip-time {
  color: #aaa;
  font-size: 0.85rem;
  margin-bottom: 4px;
}

.tooltip-title {
  color: #fff;
  font-size: 0.9rem;
  margin-bottom: 4px;
}

.tooltip-duration {
  color: #9146FF;
  font-size: 0.8rem;
  font-weight: 500;
}

/* Compact Category List */
.category-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 20px;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #18181b;
  border-radius: 8px;
  border: 1px solid #333;
  transition: all 0.2s ease;
}

.category-item:hover {
  background: #1a1a1e;
  border-color: #9146FF;
}

.category-marker {
  width: 32px;
  height: 32px;
  background: #9146FF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.category-marker .category-icon {
  color: white;
  font-size: 14px;
}

.category-details {
  flex: 1;
  min-width: 0;
}

.category-name {
  color: #fff;
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 2px;
}

.category-time {
  color: #aaa;
  font-size: 0.8rem;
}

.category-duration {
  color: #9146FF;
  font-size: 0.8rem;
  font-weight: 500;
  margin-top: 2px;
}

/* No data state */
.no-category-history {
  background: #1f1f23;
  border-radius: 12px;
  padding: 40px 20px;
  margin: 16px 0;
  border: 1px solid #333;
  text-align: center;
}

.no-data-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #888;
}

.no-data-content i {
  font-size: 2rem;
  color: #555;
}

.no-data-content p {
  margin: 0;
  font-size: 0.9rem;
}

/* Responsive design */
@media (max-width: 768px) {
  .horizontal-timeline {
    overflow-x: scroll;
    padding-bottom: 10px;
  }
  
  .timeline-tooltip {
    min-width: 150px;
    font-size: 0.85rem;
  }
  
  .category-list {
    gap: 6px;
  }
  
  .category-item {
    padding: 6px 10px;
  }
  
  .category-name {
    font-size: 0.85rem;
  }
}
</style>
