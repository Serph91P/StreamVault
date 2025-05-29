<template>
  <div class="notification-feed">
    <div class="feed-header">
      <div class="header-content">
        <div class="header-icon">
          <div class="icon-ring">
            <span class="bell-icon">🔔</span>
          </div>
        </div>
        <div class="header-text">
          <h2 class="section-title">Notifications</h2>
          <p class="section-subtitle">{{ notifications.length }} recent update{{ notifications.length !== 1 ? 's' : '' }}</p>
        </div>
      </div>
      <button 
        v-if="notifications.length > 0"
        @click="clearAllNotifications" 
        class="clear-all-btn" 
        aria-label="Clear all notifications"
      >
        <span class="clear-icon">🗑️</span>
        <span class="clear-text">Clear</span>
      </button>
    </div>
    
    <div v-if="notifications.length === 0" class="no-notifications">
      <div class="empty-state">
        <div class="empty-icon">
          <div class="icon-circle">
            <span>📭</span>
          </div>
        </div>
        <h3>All caught up!</h3>
        <p>No new notifications</p>
      </div>
    </div>
    
    <TransitionGroup v-else name="notification" tag="div" class="notification-list">
      <div v-for="notification in sortedNotifications" 
          :key="notification.id" 
          class="notification-item"
          :class="getNotificationClass(notification.type)">
        <div class="notification-indicator" :class="getNotificationClass(notification.type)"></div>
        
        <div class="notification-icon">
          <div class="icon-wrapper" :class="getNotificationClass(notification.type)">
            <span v-if="notification.type === 'stream.online'">🔴</span>
            <span v-else-if="notification.type === 'stream.offline'">⭕</span>
            <span v-else-if="notification.type === 'channel.update' || notification.type === 'stream.update'">📝</span>
            <span v-else-if="notification.type === 'recording.started'">🎥</span>
            <span v-else-if="notification.type === 'recording.completed'">✅</span>
            <span v-else-if="notification.type === 'recording.failed'">❌</span>
            <span v-else>ℹ️</span>
          </div>
        </div>
        
        <div class="notification-content">
          <div class="notification-header">
            <span class="notification-title">{{ formatTitle(notification) }}</span>
            <span class="notification-time">{{ formatTime(notification.timestamp) }}</span>
          </div>
          <p class="notification-message">{{ formatMessage(notification) }}</p>
          
          <div v-if="notification.data?.game_name || notification.data?.category_name" class="notification-meta">
            <span class="category-tag">
              <span class="tag-icon">🎮</span>
              {{ notification.data?.game_name || notification.data?.category_name }}
            </span>
          </div>
        </div>
        
        <button @click="removeNotification(notification.id)" class="notification-dismiss" aria-label="Dismiss notification">
          <span class="dismiss-icon">×</span>
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, defineEmits } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const emit = defineEmits(['notifications-read', 'close-panel'])

interface NotificationData {
  [key: string]: any;
}

interface Notification {
  id: string;
  type: string;
  timestamp: string;
  streamer_username?: string;
  title?: string;
  data?: NotificationData;
}

const notifications = ref<Notification[]>([])
const { messages } = useWebSocket()

const MAX_NOTIFICATIONS = 100

// Sort notifications by timestamp (newest first)
const sortedNotifications = computed(() => {
  return [...notifications.value].sort((a, b) => {
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  })
})

// Format relative time (e.g. "5 minutes ago")
const formatTime = (timestamp: string): string => {
  const now = new Date()
  const time = new Date(timestamp)
  const diff = now.getTime() - time.getTime()
  
  if (diff < 60 * 1000) {
    return 'Just now'
  }
  
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`
  }
  
  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000))
    return `${hours} hour${hours !== 1 ? 's' : ''} ago`
  }
  
  if (diff < 7 * 24 * 60 * 60 * 1000) {
    const days = Math.floor(diff / (24 * 60 * 60 * 1000))
    return `${days} day${days !== 1 ? 's' : ''} ago`
  }
  
  return time.toLocaleDateString()
}

// Format notification title based on type
const formatTitle = (notification: Notification): string => {
  const username = notification.streamer_username || notification.data?.streamer_name || notification.data?.username || 'Unknown'
  
  if (notification.data?.test_id) {
    return 'Test Notification'
  }
  
  switch (notification.type) {
    case 'stream.online':
      return `${username} is Live`
    case 'stream.offline':
      return `${username} Stream Ended`
    case 'channel.update':
    case 'stream.update':
      return `${username} Updated Stream`
    case 'recording.started':
      return `Recording Started`
    case 'recording.completed':
      return `Recording Completed`
    case 'recording.failed':
      return `Recording Failed`
    default:
      return notification.title || 'Notification'
  }
}

// Format notification message based on type and data
const formatMessage = (notification: Notification): string => {
  const { type, data } = notification
  const username = notification.streamer_username || data?.streamer_name || data?.username || 'Unknown'
  
  if (data?.message) {
    return data.message
  }
  
  switch (type) {
    case 'stream.online':
      return data?.title ? `${username} is live: "${data.title}"` : `${username} is now streaming`
    case 'stream.offline':
      return `${username} has gone offline`
    case 'channel.update':
    case 'stream.update':
      return data?.title ? `New title: ${data.title}` : `${username} updated their stream`
    case 'recording.started':
      return `Started recording ${username}'s stream`
    case 'recording.completed':
      return `Successfully completed recording ${username}'s stream`
    case 'recording.failed':
      return data?.error ? `Failed to record ${username}'s stream: ${data.error}` : `Failed to record ${username}'s stream`
    default:
      return `New notification for ${username}`
  }
}

// Get CSS class based on notification type
const getNotificationClass = (type: string): string => {
  switch (type) {
    case 'stream.online':
      return 'online'
    case 'stream.offline':
      return 'offline'
    case 'channel.update':
    case 'stream.update':
      return 'update'
    case 'recording.started':
      return 'recording'
    case 'recording.completed':
      return 'success'
    case 'recording.failed':
      return 'error'
    default:
      return 'info'
  }
}

// Add a new notification
const addNotification = (message: any): void => {
  console.log('🔥 NotificationFeed: ADDING NOTIFICATION:', message)
  
  try {
    const id = message.data?.test_id || crypto.randomUUID()
    
    const timestamp = message.data?.timestamp 
      ? new Date(parseInt(message.data.timestamp) || message.data.timestamp).toISOString()
      : new Date().toISOString()
    
    const streamer_username = message.data?.username || 
                             message.data?.streamer_name || 
                             'Unknown'
    
    const newNotification: Notification = {
      id,
      type: message.type,
      timestamp,
      streamer_username,
      data: message.data || {}
    }
    
    console.log('🔥 NotificationFeed: CREATED NOTIFICATION:', newNotification)
    
    // Remove duplicate
    notifications.value = notifications.value.filter(n => n.id !== id)
    
    // Add to beginning
    notifications.value.unshift(newNotification)
    
    // Limit notifications
    if (notifications.value.length > MAX_NOTIFICATIONS) {
      notifications.value = notifications.value.slice(0, MAX_NOTIFICATIONS)
    }
    
    console.log('🔥 NotificationFeed: NOTIFICATIONS ARRAY NOW HAS:', notifications.value.length, 'items')
    console.log('🔥 NotificationFeed: FIRST NOTIFICATION:', notifications.value[0])
    
    // Save to localStorage
    saveNotifications()
    
  } catch (error) {
    console.error('❌ NotificationFeed: Error adding notification:', error)
  }
}

// Remove a specific notification
const removeNotification = (id: string): void => {
  notifications.value = notifications.value.filter(n => n.id !== id)
  saveNotifications()
}

// Clear all notifications
const clearAllNotifications = (): void => {
  notifications.value = []
  saveNotifications()
}

// Save notifications to localStorage
const saveNotifications = (): void => {
  try {
    localStorage.setItem('streamvault_notifications', JSON.stringify(notifications.value))
    console.log('💾 NotificationFeed: Saved', notifications.value.length, 'notifications to localStorage')
  } catch (error) {
    console.error('❌ NotificationFeed: Error saving notifications:', error)
  }
}

// Load notifications from localStorage
const loadNotifications = (): void => {
  try {
    const saved = localStorage.getItem('streamvault_notifications')
    if (saved) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed)) {
        notifications.value = parsed
        console.log('📂 NotificationFeed: Loaded', parsed.length, 'notifications from localStorage')
      }
    }
  } catch (error) {
    console.error('❌ NotificationFeed: Error loading notifications:', error)
    notifications.value = []
  }
}

// Process WebSocket message
const processMessage = (message: any) => {
  console.log('⚡ NotificationFeed: PROCESSING MESSAGE:', message)
  
  if (!message || !message.type) {
    console.log('❌ NotificationFeed: Invalid message')
    return
  }
  
  // Skip connection status messages
  if (message.type === 'connection.status') {
    console.log('⏭️ NotificationFeed: Skipping connection status')
    return
  }
  
  // Valid notification types
  const validTypes = [
    'stream.online', 
    'stream.offline',
    'channel.update',
    'stream.update',
    'recording.started',
    'recording.completed',
    'recording.failed'
  ]
  
  if (validTypes.includes(message.type)) {
    console.log('✅ NotificationFeed: Valid message type, adding notification')
    addNotification(message)
  } else {
    console.log('❌ NotificationFeed: Invalid message type:', message.type)
  }
}

// Watch for new messages - SIMPLIFIED VERSION
let lastProcessedCount = 0

watch(messages, (newMessages) => {
  console.log('👀 NotificationFeed: Messages changed. Count:', newMessages.length, 'Last processed:', lastProcessedCount)
  
  if (newMessages.length > lastProcessedCount) {
    console.log('🆕 NotificationFeed: NEW MESSAGES DETECTED!')
    
    // Process only the new messages
    const newMessagesToProcess = newMessages.slice(lastProcessedCount)
    console.log('🆕 NotificationFeed: Processing', newMessagesToProcess.length, 'new messages')
    
    newMessagesToProcess.forEach((message, index) => {
      console.log(`🆕 NotificationFeed: Processing new message ${index + 1}:`, message)
      processMessage(message)
    })
    
    lastProcessedCount = newMessages.length
  }
}, { deep: true, immediate: true })

// On mount
onMounted(() => {
  console.log('🚀 NotificationFeed: Component mounted')
  
  // Load existing notifications
  loadNotifications()
  
  // Process any existing messages
  if (messages.value.length > 0) {
    console.log('🚀 NotificationFeed: Found', messages.value.length, 'existing messages')
    messages.value.forEach(processMessage)
    lastProcessedCount = messages.value.length
  }
  
  emit('notifications-read')
})
</script>

<style scoped>
.notification-feed {
  max-width: 400px;
  max-height: 800px;
  overflow-y: auto;
  background-color: var(--background-darker, #18181b);
  border-radius: var(--border-radius, 8px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  width: 100%;
  border: 1px solid var(--border-color, #2f2f35);
}

@keyframes slideIn {
  from {
    transform: translateY(-10px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.feed-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color, #2f2f35);
  background-color: var(--background-darker, #18181b);
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon .icon-ring {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--background-dark, #1f1f23);
  border: 2px solid var(--primary-color, #9147ff);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
}

.bell-icon {
  font-size: 16px;
}

.header-text {
  display: flex;
  flex-direction: column;
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #efeff1);
}

.section-subtitle {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: var(--text-secondary, #adadb8);
}

.clear-all-btn {
  background: none;
  border: none;
  color: var(--text-secondary, #adadb8);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: var(--border-radius, 4px);
  transition: all 0.2s ease;
}

.clear-all-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #efeff1);
}

.clear-icon {
  font-size: 14px;
}

.no-notifications {
  padding: 48px 16px;
  text-align: center;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 0;
}

.empty-state .empty-icon {
  margin-bottom: 16px;
}

.empty-state .icon-circle {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background-color: var(--background-dark, #1f1f23);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
}

.empty-state h3 {
  margin: 8px 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary, #efeff1);
}

.empty-state p {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary, #adadb8);
}

.notification-list {
  flex-grow: 1;
  overflow-y: auto;
  max-height: 550px; /* Adjust as needed */
}

.notification-list::-webkit-scrollbar {
  width: 6px;
}

.notification-list::-webkit-scrollbar-track {
  background: transparent;
}

.notification-list::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.notification-list::-webkit-scrollbar-thumb:hover {
  background-color: rgba(255, 255, 255, 0.2);
}

.notification-item {
  padding: 16px;
  border-bottom: 1px solid var(--border-color, #2f2f35);
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 12px;
  align-items: flex-start;
  animation: slideIn 0.3s ease;
}

.notification-item:last-child {
  border-bottom: none;
}

.notification-item:hover {
  background-color: rgba(255, 255, 255, 0.03);
}

.notification-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}

.notification-indicator.online {
  background-color: var(--success-color, #1db954);
}

.notification-indicator.offline {
  background-color: var(--warning-color, #ff9800);
}

.notification-indicator.update {
  background-color: var(--info-color, #00b4d8);
}

.notification-indicator.recording {
  background-color: var(--danger-color, #f44336);
}

.notification-indicator.success {
  background-color: var(--success-color, #1db954);
}

.notification-indicator.error {
  background-color: var(--danger-color, #f44336);
}

.notification-indicator.info {
  background-color: var(--info-color, #00b4d8);
}

.notification-icon {
  margin-top: 3px;
}

.icon-wrapper {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.icon-wrapper.online {
  background-color: rgba(29, 185, 84, 0.1);
  color: var(--success-color, #1db954);
}

.icon-wrapper.offline {
  background-color: rgba(255, 152, 0, 0.1);
  color: var(--warning-color, #ff9800);
}

.icon-wrapper.update {
  background-color: rgba(0, 180, 216, 0.1);
  color: var(--info-color, #00b4d8);
}

.icon-wrapper.recording {
  background-color: rgba(244, 67, 54, 0.1);
  color: var(--danger-color, #f44336);
}

.icon-wrapper.success {
  background-color: rgba(29, 185, 84, 0.1);
  color: var(--success-color, #1db954);
}

.icon-wrapper.error {
  background-color: rgba(244, 67, 54, 0.1);
  color: var(--danger-color, #f44336);
}

.icon-wrapper.info {
  background-color: rgba(0, 180, 216, 0.1);
  color: var(--info-color, #00b4d8);
}

.notification-content {
  flex: 1;
  min-width: 0; /* Ensure text wrapping */
}

.notification-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.notification-title {
  font-weight: 500;
  color: var(--text-primary, #efeff1);
  font-size: 14px;
}

.notification-time {
  color: var(--text-secondary, #adadb8);
  font-size: 12px;
}

.notification-message {
  margin: 6px 0;
  color: var(--text-secondary, #adadb8);
  font-size: 13px;
  line-height: 1.4;
  word-break: break-word;
}

.notification-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.category-tag {
  background-color: var(--background-dark, #1f1f23);
  border-radius: 16px;
  padding: 3px 8px;
  font-size: 12px;
  color: var(--text-secondary, #adadb8);
  display: flex;
  align-items: center;
  gap: 4px;
}

.tag-icon {
  font-size: 12px;
}

.notification-dismiss {
  background: none;
  border: none;
  color: var(--text-secondary, #adadb8);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 5px 8px;
  border-radius: 50%;
  margin: -5px -8px 0 0; /* Negative margin to increase hit area */
  display: flex;
  align-items: center;
  justify-content: center;
}

.notification-dismiss:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #efeff1);
}

.dismiss-icon {
  display: inline-block;
}

/* Animation transitions */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateY(-20px);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.notification-move {
  transition: transform 0.3s ease;
}

/* Responsive adjustments */
@media (max-width: 640px) {
  .notification-feed {
    width: 100%;
    max-width: 100%;
    border-radius: 0;
    height: 100%;
    max-height: none;
  }
}

/* Dark mode enhancements */
@media (prefers-color-scheme: dark) {
  .notification-feed {
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }
}
</style>
