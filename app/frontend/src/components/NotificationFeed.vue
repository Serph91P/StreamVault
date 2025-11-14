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
        @click.stop="clearAllNotifications" 
        @mousedown.stop
        @mouseup.stop
        @touchstart.stop="clearAllNotifications"
        class="clear-all-btn" 
        aria-label="Clear all notifications"
        type="button"
        ref="clearButton"
      >
        <span class="clear-icon" @click.stop="clearAllNotifications">🗑️</span>
        <span class="clear-text" @click.stop="clearAllNotifications">Clear</span>
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
          :class="getNotificationClass(notification.type, notification)">
        <div class="notification-indicator" :class="getNotificationClass(notification.type, notification)"></div>
        
        <div class="notification-icon">
          <div class="icon-wrapper" :class="getNotificationClass(notification.type, notification)">
            <!-- Toast notification icons -->
            <span v-if="notification.type === 'toast_notification' && notification.data?.toast_type === 'success'">✅</span>
            <span v-else-if="notification.type === 'toast_notification' && notification.data?.toast_type === 'error'">❌</span>
            <span v-else-if="notification.type === 'toast_notification' && notification.data?.toast_type === 'warning'">⚠️</span>
            <span v-else-if="notification.type === 'toast_notification' && notification.data?.toast_type === 'info'">ℹ️</span>
            <!-- Regular notification icons -->
            <span v-else-if="notification.type === 'stream.online'">🔴</span>
            <span v-else-if="notification.type === 'stream.offline'">⭕</span>
            <span v-else-if="notification.type === 'channel.update' || notification.type === 'stream.update'">📝</span>
            <span v-else-if="notification.type === 'recording.started'">🎥</span>
            <span v-else-if="notification.type === 'recording.completed'">✅</span>
            <span v-else-if="notification.type === 'recording.failed'">❌</span>
            <span v-else-if="notification.type === 'test'">🧪</span>
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
              <span class="category-image-small">
                <img 
                  v-if="!getCategoryImage(notification.data?.game_name || notification.data?.category_name || '').startsWith('icon:')"
                  :src="getCategoryImage(notification.data?.game_name || notification.data?.category_name || '')" 
                  :alt="notification.data?.game_name || notification.data?.category_name"
                  loading="lazy"
                />
                <i 
                  v-else 
                  :class="getCategoryImage(notification.data?.game_name || notification.data?.category_name || '').replace('icon:', '')"
                  class="category-icon"
                ></i>
              </span>
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
import { ref, computed, onMounted, onUnmounted, watch, defineEmits } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useCategoryImages } from '@/composables/useCategoryImages'
import { notificationApi } from '@/services/api'

const emit = defineEmits(['notifications-read', 'close-panel', 'clear-all'])

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
const { getCategoryImage } = useCategoryImages()

const MAX_NOTIFICATIONS = 100

// Debounce mechanism to prevent rapid duplicate notifications
const recentNotifications = new Map<string, number>()
const DEBOUNCE_TIME = 2000 // 2 seconds

// Function to generate a unique key for notifications
const generateNotificationKey = (notification: Notification): string => {
  return `${notification.type}_${notification.streamer_username}_${notification.data?.title || ''}`
}

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
  
  // Handle toast notifications
  if (notification.type === 'toast_notification') {
    return notification.data?.title || 'Notification'
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
  
  // Handle toast notifications
  if (type === 'toast_notification') {
    return data?.message || 'Toast notification'
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
      // Support both error and error_message fields
      const errorMsg = data?.error_message || data?.error || 'Unknown error'
      return `Recording failed for ${username}: ${errorMsg}`
    case 'test':
      return data?.message || 'This is a test notification to verify the system is working properly'
    default:
      return `New notification for ${username}`
  }
}

// Get CSS class based on notification type
const getNotificationClass = (type: string, notification?: Notification): string => {
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
    case 'toast_notification':
      // Use the toast_type from data if available
      return notification?.data?.toast_type || 'info'
    case 'test':
      return 'test'
    default:
      return 'info'
  }
}

// Add a new notification - IMPROVED VERSION
const addNotification = (message: any): void => {
  try {
    const id = message.data?.test_id || `${message.type}_${Date.now()}_${Math.random()}`
    
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
    
    // Check debounce to prevent rapid duplicates
    const notificationKey = generateNotificationKey(newNotification)
    const now = Date.now()
    const lastTime = recentNotifications.get(notificationKey)
    
    if (lastTime && (now - lastTime) < DEBOUNCE_TIME) {
      return
    }
    
    // Update debounce tracker
    recentNotifications.set(notificationKey, now)
    
    // Clean up old debounce entries (older than 5 minutes)
    for (const [key, time] of recentNotifications.entries()) {
      if (now - time > 300000) { // 5 minutes
        recentNotifications.delete(key)
      }
    }
    
    // Enhanced duplicate detection
    const isDuplicate = (existing: Notification, incoming: Notification): boolean => {
      // Same type and streamer
      if (existing.type !== incoming.type || existing.streamer_username !== incoming.streamer_username) {
        return false
      }
      
      // For stream updates, check if title/content is the same
      if (incoming.type === 'channel.update' || incoming.type === 'stream.update') {
        const existingTitle = existing.data?.title || ''
        const incomingTitle = incoming.data?.title || ''
        
        // If same title and within 30 seconds, it's a duplicate
        const timeDiff = Math.abs(new Date(existing.timestamp).getTime() - new Date(incoming.timestamp).getTime())
        if (existingTitle === incomingTitle && timeDiff < 30000) {
          return true
        }
      }
      
      // For stream.online, check within 10 seconds
      if (incoming.type === 'stream.online') {
        const timeDiff = Math.abs(new Date(existing.timestamp).getTime() - new Date(incoming.timestamp).getTime())
        return timeDiff < 10000
      }
      
      // For recording events, check within 5 seconds
      if (incoming.type.startsWith('recording.')) {
        const timeDiff = Math.abs(new Date(existing.timestamp).getTime() - new Date(incoming.timestamp).getTime())
        return timeDiff < 5000
      }
      
      return false
    }
    
    // Find existing duplicate
    const existingIndex = notifications.value.findIndex(n => isDuplicate(n, newNotification))
    
    if (existingIndex >= 0) {
      notifications.value[existingIndex] = newNotification
    } else {
      // Add to beginning
      notifications.value.unshift(newNotification)
    }
    
    // Limit notifications
    if (notifications.value.length > MAX_NOTIFICATIONS) {
      notifications.value = notifications.value.slice(0, MAX_NOTIFICATIONS)
    }
    
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
const clearAllNotifications = async (event?: Event): Promise<void> => {
  // Prevent any default behavior or propagation
  if (event) {
    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()
  }
  
  try {
    // Clear on backend (sets last_cleared_timestamp in DB)
    await notificationApi.clear()
    console.log('✅ NotificationFeed: Backend cleared successfully')
  } catch (error) {
    console.error('❌ NotificationFeed: Failed to clear on backend:', error)
  }
  
  // Clear notifications directly
  notifications.value = []
  
  // Clear localStorage immediately
  try {
    localStorage.removeItem('streamvault_notifications')
    localStorage.setItem('streamvault_notifications', JSON.stringify([]))
  } catch (error) {
    console.error('❌ NotificationFeed: Error clearing localStorage:', error)
  }
  
  // Dispatch event immediately
  window.dispatchEvent(new CustomEvent('notificationsUpdated', {
    detail: { count: 0 }
  }))
  
  // Also emit to App.vue for any additional cleanup
  emit('clear-all')
  
  // Close the panel after clearing
  emit('close-panel')
}

// Save notifications to localStorage
const saveNotifications = (): void => {
  try {
    localStorage.setItem('streamvault_notifications', JSON.stringify(notifications.value))

    
    // Dispatch a custom event to notify other components (like App.vue) that notifications changed
    window.dispatchEvent(new CustomEvent('notificationsUpdated', {
      detail: { count: notifications.value.length }
    }))
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
      
      if (Array.isArray(parsed) && parsed.length > 0) {
        notifications.value = parsed
      } else {
        notifications.value = []
      }
    } else {
      notifications.value = []

    }
  } catch (error) {
    console.error('❌ NotificationFeed: Error loading notifications:', error)
    notifications.value = []
  }
}

// Process WebSocket message
const processMessage = (message: any): void => {
  if (!message || !message.type) {
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
    'recording.failed',
    'toast_notification', // Add toast notification support
    'test' // Add test type
  ]
  
  if (validTypes.includes(message.type)) {
    console.log('✅ NotificationFeed: Valid message type, adding notification')
    addNotification(message)
  } else {
    console.log('❌ NotificationFeed: Invalid message type:', message.type)
  }
}

// Track previous message count to detect actual changes
const previousMessageCount = ref(0)

// Watch for new messages - IMPROVED VERSION
watch(() => messages.value.length, (newLength: number) => {
  console.log('🔥 NotificationFeed: Message count changed to', newLength, 'from', previousMessageCount.value)
  
  if (newLength > previousMessageCount.value) {
    console.log('🔥 NotificationFeed: NEW MESSAGES DETECTED!')
    
    // Process only the new messages since last check
    const newCount = newLength - previousMessageCount.value
    const messagesToProcess = messages.value.slice(-newCount)
    console.log('🔥 NotificationFeed: Processing', messagesToProcess.length, 'new messages')
    
    messagesToProcess.forEach((message: any, index: number) => {
      console.log(`🔥 NotificationFeed: Processing new message ${index + 1}:`, message)
      processMessage(message)
    })
    
    // Update our counter for next time
    previousMessageCount.value = newLength
  }
}, { immediate: false }) // Don't process immediately to avoid double processing

// On mount
onMounted(async () => {
  console.log('🚀 NotificationFeed: Component mounted')
  
  // Load backend notification state (last_cleared_timestamp)
  let lastClearedTimestamp: number | null = null
  try {
    const backendState = await notificationApi.getState()
    if (backendState.last_cleared_timestamp) {
      lastClearedTimestamp = new Date(backendState.last_cleared_timestamp).getTime()
      console.log('🚀 NotificationFeed: Backend last cleared:', new Date(lastClearedTimestamp).toISOString())
    }
  } catch (error) {
    console.error('❌ NotificationFeed: Failed to load backend state:', error)
  }
  
  // Load existing notifications from localStorage FIRST
  loadNotifications()
  
  // Filter out notifications that were cleared on backend
  if (lastClearedTimestamp) {
    const beforeFilter = notifications.value.length
    notifications.value = notifications.value.filter(n => {
      const notifTime = new Date(n.timestamp).getTime()
      return notifTime > lastClearedTimestamp!
    })
    const afterFilter = notifications.value.length
    if (beforeFilter !== afterFilter) {
      console.log(`🚀 NotificationFeed: Filtered ${beforeFilter - afterFilter} cleared notifications`)
      saveNotifications() // Update localStorage
    }
  }
  
  // Set the initial message count to current messages length
  previousMessageCount.value = messages.value.length
  console.log('🚀 NotificationFeed: Set initial message count to', previousMessageCount.value)
  
  // Process ALL existing WebSocket messages (they may not be in localStorage yet)
  console.log('🚀 NotificationFeed: Processing', messages.value.length, 'existing WebSocket messages')
  messages.value.forEach((message: any, index: number) => {
    console.log(`🚀 NotificationFeed: Processing existing message ${index + 1}:`, message)
    processMessage(message)
  })
  console.log('🚀 NotificationFeed: Component fully loaded with', notifications.value.length, 'notifications')
  
  // Listen for external notification updates (like clear all from App.vue)
  window.addEventListener('notificationsUpdated', handleNotificationsUpdated)
  
  // DON'T auto-mark as read - let the user see the notifications until they manually close the panel
})

// Handle external notification updates
const handleNotificationsUpdated = (event: any) => {
  console.log('📡 NotificationFeed: Received notificationsUpdated event:', event.detail)
  // Reload notifications from localStorage to stay in sync
  loadNotifications()
}

// Mark notifications as read when component is unmounted (panel closes)
onUnmounted(() => {
  console.log('🚀 NotificationFeed: Component unmounting, marking notifications as read')
  // Remove event listener
  window.removeEventListener('notificationsUpdated', handleNotificationsUpdated)
  emit('notifications-read')
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.notification-feed {
  max-width: 400px;
  max-height: 800px;
  overflow-y: auto;
  background: rgba(var(--background-card-rgb), 0.95);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-2xl);
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  width: 100%;
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
  position: relative;
  z-index: 10;
  pointer-events: auto;
  user-select: none;
  -webkit-user-select: none;
}

.clear-all-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #efeff1);
  transform: scale(1.05);
}

.clear-all-btn:active {
  transform: scale(0.95);
  background-color: rgba(255, 255, 255, 0.2);
}

.clear-all-btn:focus {
  outline: 2px solid rgba(255, 255, 255, 0.3);
  outline-offset: 2px;
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
  margin: var(--spacing-2) var(--spacing-3);
  border-radius: var(--radius-lg);
  background: rgba(var(--background-darker-rgb), 0.4);
  border: 1px solid rgba(255, 255, 255, 0.05);
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 12px;
  align-items: flex-start;
  animation: slideIn 0.3s ease;
  transition: all var(--duration-200) var(--ease-out);
}

.notification-item:hover {
  background: rgba(var(--background-darker-rgb), 0.6);
  border-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}

.notification-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  opacity: 0.5;
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

.notification-indicator.test {
  background-color: var(--purple-color, #9147ff);
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

.icon-wrapper.test {
  background-color: rgba(145, 71, 255, 0.1);
  color: var(--purple-color, #9147ff);
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

.category-image-small {
  width: 16px;
  height: 16px;
  border-radius: 2px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.category-image-small img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.category-image-small .category-icon {
  font-size: 12px;
  color: #9146ff;
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

/* Mobile responsiveness */
@include m.respond-below('md') {  // < 768px
  .notification-feed {
    width: 100vw;
    max-width: 100vw;
    height: 100vh;
    max-height: 100vh;
    border-radius: 0;
    position: fixed;
    top: 0;
    left: 0;
    z-index: 1000;
    overflow: hidden;
  }
  
  .feed-header {
    padding: 16px 20px;
    border-bottom: 2px solid var(--border-color, #2f2f35);
    background: var(--background-darker, #18181b);
    position: sticky;
    top: 0;
    z-index: 10;
  }
  
  .header-content {
    align-items: center;
  }
  
  .header-icon .icon-ring {
    width: 28px;
    height: 28px;
  }
  
  .bell-icon {
    font-size: 14px;
  }
  
  .section-title {
    font-size: 18px;
    font-weight: 700;
  }
  
  .section-subtitle {
    font-size: 13px;
    margin-top: 2px;
  }
  
  .clear-all-btn {
    padding: 8px 12px;
    font-size: 14px;
    min-height: 44px;
    border-radius: 8px;
    touch-action: manipulation;
  }
  
  .clear-all-btn:active {
    transform: scale(0.98);
  }
  
  .notification-list {
    flex-grow: 1;
    overflow-y: auto;
    max-height: calc(100vh - 80px);
    -webkit-overflow-scrolling: touch;
  }
  
  .notification-item {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color, #2f2f35);
    grid-template-columns: auto 1fr auto;
    gap: 14px;
    align-items: flex-start;
  }
  
  .notification-icon {
    margin-top: 2px;
  }
  
  .icon-wrapper {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }
  
  .notification-content {
    flex: 1;
    min-width: 0;
    padding-right: 8px;
  }
  
  .notification-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 6px;
  }
  
  .notification-title {
    font-size: 15px;
    font-weight: 600;
    line-height: 1.3;
  }
  
  .notification-time {
    font-size: 12px;
    opacity: 0.8;
  }
  
  .notification-message {
    font-size: 14px;
    line-height: 1.4;
    margin: 8px 0;
    word-break: break-word;
  }
  
  .notification-meta {
    margin-top: 10px;
  }
  
  .category-tag {
    padding: 4px 8px;
    font-size: 11px;
    border-radius: 12px;
  }
  
  .category-image-small {
    width: 14px;
    height: 14px;
  }
  
  .notification-dismiss {
    padding: 8px;
    font-size: 20px;
    width: 36px;
    height: 36px;
    margin: -4px -8px 0 0;
    touch-action: manipulation;
    border-radius: 50%;
  }
  
  .notification-dismiss:active {
    transform: scale(0.95);
  }
  
  .empty-state {
    padding: 60px 20px;
  }
  
  .empty-state .icon-circle {
    width: 80px;
    height: 80px;
    font-size: 40px;
    margin: 0 auto 20px;
  }
  
  .empty-state h3 {
    font-size: 20px;
    margin: 16px 0 8px;
  }
  
  .empty-state p {
    font-size: 16px;
  }
}

/* Extra small screens (phones in portrait) */
@include m.respond-below('xs') {  // < 480px
  .feed-header {
    padding: 12px 16px;
  }
  
  .section-title {
    font-size: 16px;
  }
  
  .section-subtitle {
    font-size: 12px;
  }
  
  .clear-all-btn {
    padding: 6px 10px;
    font-size: 13px;
  }
  
  .notification-item {
    padding: 14px 16px;
    gap: 12px;
  }
  
  .icon-wrapper {
    width: 32px;
    height: 32px;
    font-size: 16px;
  }
  
  .notification-title {
    font-size: 14px;
  }
  
  .notification-message {
    font-size: 13px;
  }
  
  .notification-dismiss {
    width: 32px;
    height: 32px;
    font-size: 18px;
  }
  
  .empty-state {
    padding: 40px 16px;
  }
  
  .empty-state .icon-circle {
    width: 60px;
    height: 60px;
    font-size: 30px;
  }
  
  .empty-state h3 {
    font-size: 18px;
  }
  
  .empty-state p {
    font-size: 14px;
  }
}

/* Landscape phones */
@media (max-width: 767px) and (orientation: landscape) {  // Cannot use mixins for orientation queries
  .notification-list {
    max-height: calc(100vh - 70px);
  }
  
  .notification-item {
    padding: 12px 20px;
  }
  
  .empty-state {
    padding: 30px 20px;
  }
}

/* Dark mode enhancements */
@media (prefers-color-scheme: dark) {
  .notification-feed {
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }
}
</style>
