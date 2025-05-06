<template>
  <div class="notification-feed">
    <h2 class="section-title">Recent Notifications</h2>
    
    <div v-if="notifications.length === 0" class="empty-state">
      <div class="empty-icon">📬</div>
      <p>No notifications yet</p>
    </div>
    
    <TransitionGroup name="notification" tag="ul" class="notification-list" v-else>
      <li v-for="notification in sortedNotifications" 
          :key="notification.id" 
          class="notification-item"
          :class="getNotificationClass(notification.type)">
        <div class="notification-icon">
          <div class="icon-wrapper" :class="getNotificationClass(notification.type)">
            <span v-if="notification.type === 'stream.online'">🔴</span>
            <span v-else-if="notification.type === 'stream.offline'">⭕</span>
            <span v-else-if="notification.type === 'channel.update'">📝</span>
            <span v-else-if="notification.type === 'recording.started'">🎥</span>
            <span v-else-if="notification.type === 'recording.completed'">✅</span>
            <span v-else-if="notification.type === 'recording.failed'">❌</span>
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
    
    <div class="notification-actions" v-if="notifications.length > 0">
      <button @click="clearAllNotifications" class="btn btn-secondary">
        Clear All
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

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

const MAX_NOTIFICATIONS = 50

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
      return `${username} Updated Stream`
    case 'recording.started':
      return `Recording Started`
    case 'recording.completed':
      return `Recording Completed`
    case 'recording.failed':
      return `Recording Failed`
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
      return 'update'
    case 'recording.started':
      return 'recording'
    case 'recording.completed':
      return 'success'
    case 'recording.failed':
      return 'error'
    default:
      return 'default'
  }
}

// Add a new notification from WebSocket message
const addNotification = (message: any): void => {
  const id = crypto.randomUUID()
  
  notifications.value.unshift({
    id,
    type: message.type,
    timestamp: new Date().toISOString(),
    streamer_username: message.data?.username,
    data: message.data
  })
  
  // Limit the number of notifications
  if (notifications.value.length > MAX_NOTIFICATIONS) {
    notifications.value = notifications.value.slice(0, MAX_NOTIFICATIONS)
  }
  
  // Save to localStorage
  saveNotifications()
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

// Watch for WebSocket messages
const messageWatcher = (newMessages: any[]) => {
  if (newMessages.length === 0) return
  
  const latestMessage = newMessages[newMessages.length - 1]
  console.log('NotificationFeed: New WebSocket message:', latestMessage)
  
  // Only process certain notification types
  const notificationTypes = [
    'stream.online', 
    'stream.offline', 
    'channel.update',
    'recording.started',
    'recording.completed',
    'recording.failed'
  ]
  
  if (notificationTypes.includes(latestMessage.type)) {
    addNotification(latestMessage)
  }
}

// Lifecycle hooks
onMounted(() => {
  loadNotifications()
  
  // Watch for new messages
  const unwatch = messages.value ? messages.value.$subscribe(messageWatcher) : null;
  
  if (messages.value) {
    messages.value.$subscribe(messageWatcher)
  }
})

onBeforeUnmount(() => {
  // Cleanup if needed
})
</script>

<style scoped>
.notification-feed {
  padding: var(--spacing-md);
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-sm);
  max-width: 100%;
  overflow: hidden;
}

.section-title {
  margin-top: 0;
  margin-bottom: var(--spacing-md);
  color: var(--text-primary);
  font-size: 1.2rem;
  font-weight: 600;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: var(--spacing-sm);
}

.notification-list {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 500px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--primary-color) var(--background-dark);
}

.notification-list::-webkit-scrollbar {
  width: 6px;
}

.notification-list::-webkit-scrollbar-track {
  background: var(--background-dark);
  border-radius: 3px;
}

.notification-list::-webkit-scrollbar-thumb {
  background-color: var(--primary-color-muted);
  border-radius: 3px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  padding: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
  background-color: var(--background-card);
  border-radius: var(--border-radius-sm);
  position: relative;
  transition: all 0.3s var(--vue-ease);
  border-left: 3px solid transparent;
}

.notification-item:last-child {
  margin-bottom: 0;
}

.notification-item:hover {
  box-shadow: var(--shadow-sm);
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

.notification-icon {
  flex-shrink: 0;
  margin-right: var(--spacing-sm);
}

.icon-wrapper {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--background-dark);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
}

.icon-wrapper.online {
  background-color: rgba(220, 53, 69, 0.15);
}

.icon-wrapper.offline {
  background-color: rgba(108, 117, 125, 0.15);
}

.icon-wrapper.update {
  background-color: rgba(66, 184, 131, 0.15);
}

.icon-wrapper.recording {
  background-color: rgba(255, 193, 7, 0.15);
}

.icon-wrapper.success {
  background-color: rgba(40, 167, 69, 0.15);
}

.icon-wrapper.error {
  background-color: rgba(220, 53, 69, 0.15);
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--spacing-xs);
}

.notification-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.notification-time {
  font-size: 0.8rem;
  color: var(--text-muted-color);
  white-space: nowrap;
  margin-left: var(--spacing-xs);
}

.notification-message {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
  line-height: 1.4;
}

.notification-category {
  display: inline-block;
  font-size: 0.8rem;
  padding: 2px 6px;
  background-color: var(--background-dark);
  color: var(--text-muted-color);
  border-radius: 4px;
}

.notification-dismiss {
  background: none;
  border: none;
  color: var(--text-muted-color);
  font-size: 1.2rem;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  opacity: 0.5;
  margin-left: var(--spacing-xs);
  transition: opacity 0.2s var(--vue-ease);
}

.notification-dismiss:hover {
  opacity: 1;
  color: var(--danger-color);
}

.notification-actions {
  display: flex;
  justify-content: center;
  margin-top: var(--spacing-md);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-lg);
  color: var(--text-secondary);
  text-align: center;
}

.empty-icon {
  font-size: 2rem;
  margin-bottom: var(--spacing-sm);
  opacity: 0.7;
}

/* Animation transitions */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s var(--vue-ease);
}

.notification-enter-from {
  opacity: 0;
  transform: translateY(-20px);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.notification-move {
  transition: transform 0.4s var(--vue-ease);
}

/* Responsive adjustments */
@media (max-width: 640px) {
  .notification-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .notification-time {
    margin-left: 0;
    margin-top: 2px;
  }
}
</style>
