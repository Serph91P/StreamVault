<template>
  <div class="notification-feed">
    <h2 class="section-title">
      Recent Notifications
      <button @click="clearAllNotifications" class="clear-all-btn" aria-label="Clear all notifications">
        <span class="clear-all-text">Clear All</span>
      </button>
    </h2>
    
    <div v-if="notifications.length === 0" class="no-notifications">
      <div class="empty-icon">🔔</div>
      <p>No notifications yet</p>
    </div>
    
    <TransitionGroup v-else name="notification" tag="ul" class="notification-list">
      <li v-for="notification in sortedNotifications" 
          :key="notification.id" 
          class="notification-item"
          :class="getNotificationClass(notification.type)">
        <div class="notification-icon">
          <div class="icon-wrapper" :class="getNotificationClass(notification.type)">
            <span v-if="notification.type === 'stream.online'">🔴</span>
            <span v-else-if="notification.type === 'stream.offline'">⭕</span>
            <span v-else-if="notification.type === 'channel.update' || notification.type === 'stream.update'">📝</span>
            <span v-else-if="notification.type === 'recording.started'">🎥</span>
            <span v-else-if="notification.type === 'recording.completed'">✅</span>
            <span v-else-if="notification.type === 'recording.failed'">❌</span>
            <span v-else-if="notification.type === 'connection.status'">🔌</span>
            <span v-else>📣</span>
          </div>
        </div>
        
        <div class="notification-content">
          <div class="notification-header">
            <h3 class="notification-title">{{ formatTitle(notification) }}</h3>
            <span class="notification-time">{{ formatTime(notification.timestamp) }}</span>
          </div>
          
          <div class="notification-message">{{ formatMessage(notification) }}</div>
          
          <div v-if="notification.data && notification.data.category_name" class="notification-category">
            {{ notification.data.category_name }}
          </div>
        </div>
        
        <button 
          @click="removeNotification(notification.id)" 
          class="notification-dismiss"
          aria-label="Dismiss notification"
        >
          ×
        </button>
      </li>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUpdated, watch, defineEmits } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const emit = defineEmits(['notifications-read'])

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
  
  // Less than a minute
  if (diff < 60 * 1000) {
    return 'Just now'
  }
  
  // Less than an hour
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`
  }
  
  // Less than a day
  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000))
    return `${hours} hour${hours !== 1 ? 's' : ''} ago`
  }
  
  // Less than a week
  if (diff < 7 * 24 * 60 * 60 * 1000) {
    const days = Math.floor(diff / (24 * 60 * 60 * 1000))
    return `${days} day${days !== 1 ? 's' : ''} ago`
  }
  
  // Format as date
  return time.toLocaleDateString()
}

// Format notification title based on type
const formatTitle = (notification: Notification): string => {
  const username = notification.streamer_username || 'Unknown'
  
  switch (notification.type) {
    case 'stream.online':
      return `${username} is Live!`
    case 'stream.offline':
      return `${username} Ended Stream`
    case 'channel.update':
    case 'stream.update':
      return `${username} Updated Stream`
    case 'recording.started':
      return `Recording Started`
    case 'recording.completed':
      return `Recording Completed`
    case 'recording.failed':
      return `Recording Failed`
    case 'connection.status':
      return 'Connection Status'
    default:
      return `Notification for ${username}`
  }
}

// Format notification message based on type and data
const formatMessage = (notification: Notification): string => {
  const { type, data, title } = notification
  const username = notification.streamer_username || 'Unknown'
  
  switch (type) {
    case 'stream.online':
      return data?.title 
        ? `${username} started streaming: ${data.title}` 
        : `${username} is now live!`
    case 'stream.offline':
      return `${username} has ended their stream.`
    case 'channel.update':
    case 'stream.update':
      return data?.title 
        ? `Stream updated: ${data.title}` 
        : `${username} updated their stream.`
    case 'recording.started':
      return `Started recording ${username}'s stream.`
    case 'recording.completed':
      return `Successfully completed recording ${username}'s stream.`
    case 'recording.failed':
      return data?.error 
        ? `Failed to record ${username}'s stream: ${data.error}` 
        : `Failed to record ${username}'s stream.`
    case 'connection.status':
      return data?.message || 'WebSocket connection status updated.'
    default:
      return title || `New notification for ${username}`
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
    case 'connection.status':
      return 'info'
    default:
      return 'default'
  }
}

// Add a new notification from WebSocket message
const addNotification = (message: any): void => {
  const id = crypto.randomUUID()
  
  console.log('📝 NotificationFeed: Adding notification with ID:', id)
  console.log('📝 NotificationFeed: Message data:', message)
  
  const newNotification = {
    id,
    type: message.type,
    timestamp: new Date().toISOString(),
    streamer_username: message.data?.username || message.data?.streamer_name || message.streamer_username,
    data: message.data
  }
  
  console.log('📝 NotificationFeed: Created notification object:', newNotification)
  
  notifications.value.unshift(newNotification)
  
  console.log('📝 NotificationFeed: Notifications array before limit check:', notifications.value.length)
  
  // Limit the number of notifications
  if (notifications.value.length > MAX_NOTIFICATIONS) {
    notifications.value = notifications.value.slice(0, MAX_NOTIFICATIONS)
    console.log('📝 NotificationFeed: Trimmed notifications to:', notifications.value.length)
  }
  
  // Save to localStorage
  saveNotifications()
  
  console.log('✅ NotificationFeed: Total notifications after adding:', notifications.value.length)
  console.log('✅ NotificationFeed: Current notifications:', notifications.value)
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
  emit('notifications-read')
}

// Save notifications to localStorage
const saveNotifications = (): void => {
  localStorage.setItem('streamvault_notifications', JSON.stringify(notifications.value))
}

// Load notifications from localStorage
const loadNotifications = (): void => {
  const saved = localStorage.getItem('streamvault_notifications')
  if (saved) {
    try {
      notifications.value = JSON.parse(saved)
    } catch (e) {
      console.error('Failed to load notifications:', e)
    }
  }
}

// Process new WebSocket messages
const processNewMessage = (message: any) => {
  console.log('🔔 NotificationFeed: Processing new WebSocket message:', message)
  
  // Only process certain notification types
  const notificationTypes = [
    'stream.online', 
    'stream.offline', 
    'channel.update',
    'stream.update',
    'recording.started',
    'recording.completed',
    'recording.failed',
    'connection.status'
  ]
  
  console.log('🔍 NotificationFeed: Checking message type:', message.type, 'against:', notificationTypes)
  
  if (notificationTypes.includes(message.type)) {
    console.log('✅ NotificationFeed: Message type accepted, adding notification')
    addNotification(message)
  } else {
    console.warn('❌ NotificationFeed: Message type not in allowed list:', message.type)
  }
}

// Emit notifications-read event when component becomes visible
onUpdated(() => {
  if (document.visibilityState === 'visible') {
    emit('notifications-read')
  }
})

// Lifecycle hooks
onMounted(() => {
  loadNotifications()
  
  // Emit notifications-read when first mounted
  emit('notifications-read')
  
  // Watch for new messages being added to the array
  watch(messages, (newMessages, oldMessages) => {
    console.log('NotificationFeed: Messages watched triggered', { newMessages: newMessages?.length, oldMessages: oldMessages?.length })
    
    if (!newMessages || newMessages.length === 0) {
      console.log('NotificationFeed: No messages to process')
      return
    }
    
    // If there are more messages than before, process only the new ones
    if (oldMessages && newMessages.length > oldMessages.length) {
      const newMessage = newMessages[newMessages.length - 1]
      console.log('NotificationFeed: Processing new message:', newMessage)
      processNewMessage(newMessage)
    } else if (!oldMessages || oldMessages.length === 0) {
      // Initial load - process all messages
      console.log('NotificationFeed: Initial load, processing all messages')
      newMessages.forEach(message => processNewMessage(message))
    } else if (oldMessages && newMessages.length === oldMessages.length && newMessages.length > 0) {
      // Check if the latest message is different (WebSocket reconnection case)
      const latestMessage = newMessages[newMessages.length - 1]
      const previousLatestMessage = oldMessages[oldMessages.length - 1]
      
      if (latestMessage && (!previousLatestMessage || 
          latestMessage.type !== previousLatestMessage.type ||
          JSON.stringify(latestMessage.data) !== JSON.stringify(previousLatestMessage.data))) {
        console.log('NotificationFeed: Processing updated message:', latestMessage)
        processNewMessage(latestMessage)
      }
    }
  }, { deep: true, immediate: true })
})
</script>

<style scoped>
.notification-feed {
  padding: var(--spacing-md);
  background-color: rgba(var(--background-darker-rgb, 31, 31, 35), 0.95);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-md);
  max-width: 400px;
  width: 100%;
  overflow: hidden;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(var(--border-color-rgb, 45, 45, 53), 0.7);
  position: absolute;
  top: 60px;
  right: 20px;
  z-index: 1000;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.no-notifications {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--text-secondary);
  text-align: center;
}

.empty-icon {
  font-size: 2rem;
  margin-bottom: 1rem;
  opacity: 0.7;
}

.section-title {
  margin-top: 0;
  margin-bottom: var(--spacing-md);
  color: var(--text-primary);
  font-size: 1.1rem;
  font-weight: 600;
  border-bottom: 1px solid rgba(var(--border-color-rgb, 45, 45, 53), 0.7);
  padding-bottom: var(--spacing-sm);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.clear-all-btn {
  background: none;
  border: none;
  color: var(--primary-color);
  font-size: 0.85rem;
  cursor: pointer;
  opacity: 0.8;
  transition: opacity 0.2s var(--vue-ease);
  padding: 2px 6px;
  border-radius: var(--border-radius-sm);
}

.clear-all-btn:hover {
  opacity: 1;
  background-color: rgba(var(--primary-color-rgb, 66, 184, 131), 0.1);
}

.notification-list {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: calc(80vh - 60px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--primary-color-muted) transparent;
}

.notification-list::-webkit-scrollbar {
  width: 4px;
}

.notification-list::-webkit-scrollbar-track {
  background: transparent;
}

.notification-list::-webkit-scrollbar-thumb {
  background-color: var(--primary-color-muted);
  border-radius: 2px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  padding: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
  background-color: rgba(var(--background-card-rgb, 37, 37, 42), 0.7);
  border-radius: var(--border-radius-sm);
  position: relative;
  transition: all 0.2s var(--vue-ease);
  border-left: 3px solid transparent;
}

.notification-item:last-child {
  margin-bottom: 0;
}

.notification-item:hover {
  background-color: var(--background-card);
  transform: translateX(2px);
}

.notification-item.online {
  border-left-color: var(--danger-color);
}

.notification-item.offline {
  border-left-color: var(--text-secondary);
}

.notification-item.update {
  border-left-color: var(--primary-color);
}

.notification-item.recording {
  border-left-color: var(--warning-color);
}

.notification-item.success {
  border-left-color: var(--success-color);
}

.notification-item.error {
  border-left-color: var(--danger-color);
}

.notification-item.info {
  border-left-color: var(--info-color, #0ea5e9);
}

.notification-icon {
  flex-shrink: 0;
  margin-right: var(--spacing-sm);
}

.icon-wrapper {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: var(--background-dark);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
}

.icon-wrapper.online {
  background-color: rgba(255, 0, 0, 0.2);
}

.icon-wrapper.offline {
  background-color: rgba(150, 150, 150, 0.2);
}

.icon-wrapper.update {
  background-color: rgba(66, 184, 131, 0.2);
}

.icon-wrapper.recording {
  background-color: rgba(255, 165, 0, 0.2);
}

.icon-wrapper.success {
  background-color: rgba(66, 184, 131, 0.2);
}

.icon-wrapper.error {
  background-color: rgba(255, 0, 0, 0.2);
}

.icon-wrapper.info {
  background-color: rgba(14, 165, 233, 0.2);
}

.notification-content {
  flex: 1;
  min-width: 0; /* Ensure text wrapping works correctly */
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-xs);
}

.notification-title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.notification-time {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  margin-left: var(--spacing-sm);
}

.notification-message {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
  word-break: break-word;
}

.notification-category {
  display: inline-block;
  font-size: 0.75rem;
  padding: 2px 6px;
  background-color: rgba(var(--border-color-rgb, 45, 45, 53), 0.5);
  border-radius: 4px;
  color: var(--text-secondary);
}

.notification-dismiss {
  background: none;
  border: none;
  color: var(--text-secondary);
  opacity: 0.6;
  cursor: pointer;
  font-size: 1.2rem;
  line-height: 1;
  padding: 0;
  margin: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s var(--vue-ease);
}

.notification-dismiss:hover {
  opacity: 1;
  background-color: rgba(255, 255, 255, 0.1);
}

/* Animation transitions */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}

.notification-move {
  transition: transform 0.3s ease;
}

/* Responsive adjustments */
@media (max-width: 640px) {
  .notification-feed {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    max-width: none;
    max-height: none;
    border-radius: 0;
    z-index: 1001;
  }
  
  .notification-list {
    max-height: calc(100vh - 60px);
  }
}
</style>
