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
          
          <div v-if="notification.data && notification.data.category_name" class="notification-meta">
            <span class="category-tag">
              <span class="tag-icon">🎮</span>
              {{ notification.data.category_name }}
            </span>
          </div>
        </div>
        
        <button 
          @click="removeNotification(notification.id)" 
          class="notification-dismiss"
          aria-label="Dismiss notification"
        >
          <span class="dismiss-icon">×</span>
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUpdated, watch, defineEmits } from 'vue'
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
  
  // Check if this is a test notification by looking at test_id
  if (notification.data?.test_id) {
    return `🧪 Test Notification`
  }
  
  switch (notification.type) {
    case 'stream.online':
      return `${username} is Live!`
    case 'stream.offline':
      return `${username} Ended Stream`
    case 'channel.update':
    case 'stream.update':
      return username === 'TestUser' ? '🧪 Test Notification' : `${username} Updated Stream`
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
  
  // Wenn eine direkte Nachricht vorhanden ist, diese bevorzugen
  if (data?.message) {
    return data.message;
  }
  
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
    case 'test':
      return 'success' // Test notifications use the success style
    default:
      return 'default'
  }
}

// Add a new notification from WebSocket message
const addNotification = (message: any): void => {
  try {
    // Make sure we have a valid message object
    if (!message || !message.type) {
      console.error('❌ NotificationFeed: Invalid message object:', message)
      return;
    }
    
    // Use the test_id as ID if available, otherwise generate a new UUID
    const id = message.data?.test_id || crypto.randomUUID()
    
    console.log('📝 NotificationFeed: Adding notification with ID:', id)
    console.log('📝 NotificationFeed: Message data:', message)
    
    // Create a properly formatted timestamp
    let timestamp: string;
    if (message.data?.timestamp) {
      // Check if the timestamp is a number (milliseconds) or already a string date
      if (typeof message.data.timestamp === 'number' || !isNaN(parseInt(message.data.timestamp))) {
        timestamp = new Date(parseInt(message.data.timestamp)).toISOString();
      } else {
        // Try to parse the timestamp directly if it's already a date string
        try {
          timestamp = new Date(message.data.timestamp).toISOString();
        } catch (e) {
          timestamp = new Date().toISOString();
        }
      }
    } else {
      timestamp = new Date().toISOString();
    }
    
    // Extract username properly
    const streamer_username = message.data?.username || 
                             message.data?.streamer_name || 
                             message.streamer_username ||
                             'Unknown';
    
    const newNotification = {
      id,
      type: message.type,
      timestamp,
      streamer_username,
      data: message.data || {}
    }
    
    console.log('📝 NotificationFeed: Created notification object:', newNotification)
    
    // Prevent duplicates
    const existingIndex = notifications.value.findIndex(n => n.id === id)
    if (existingIndex >= 0) {
      console.log('📝 NotificationFeed: Duplicate notification detected, replacing:', id)
      notifications.value.splice(existingIndex, 1)
    }
    
    // Add at beginning of array
    notifications.value = [newNotification, ...notifications.value]
    
    console.log('📝 NotificationFeed: Notifications array before limit check:', notifications.value.length)
    
    // Limit the number of notifications
    if (notifications.value.length > MAX_NOTIFICATIONS) {
      notifications.value = notifications.value.slice(0, MAX_NOTIFICATIONS)
      console.log('📝 NotificationFeed: Trimmed notifications to:', notifications.value.length)
    }
    
    // Save to localStorage immediately to ensure persistence
    saveNotifications()
    
    // Output debug info about the notifications we now have
    console.log('✅ NotificationFeed: Total notifications after adding:', notifications.value.length)
    console.log('✅ NotificationFeed: Current notifications:', notifications.value)
    
    // Verify notifications were saved correctly with a small delay
    setTimeout(() => {
      try {
        const saved = localStorage.getItem('streamvault_notifications')
        if (saved) {
          const savedNotifications = JSON.parse(saved)
          console.log('✅ NotificationFeed: Saved to localStorage count:', savedNotifications.length)
          
          if (savedNotifications.length !== notifications.value.length) {
            console.warn('⚠️ NotificationFeed: Storage count mismatch, forcing save again')
            saveNotifications()
          }
        } else {
          console.warn('⚠️ NotificationFeed: No notifications in localStorage after save, forcing save')
          saveNotifications()
        }
      } catch (err) {
        console.error('❌ NotificationFeed: Error verifying localStorage:', err)
      }
    }, 100)
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
  try {
    console.log('🧹 NotificationFeed: Starting clear all notifications process')
    
    // Clear the notifications array
    notifications.value = []
    
    // Save empty notifications array to localStorage
    localStorage.setItem('streamvault_notifications', JSON.stringify([]))
    console.log('🧹 NotificationFeed: Cleared all notifications from localStorage')
    
    // Double-check localStorage was properly cleared
    const saved = localStorage.getItem('streamvault_notifications')
    console.log('🧹 NotificationFeed: Verification - localStorage now contains:', saved)
    
    // Emit events to update UI
    emit('notifications-read')
    console.log('🧹 NotificationFeed: Emitted notifications-read event')
    
    // Add a small delay before closing panel to ensure animations complete properly
    setTimeout(() => {
      console.log('🧹 NotificationFeed: Closing notification panel')
      emit('close-panel') // Close the notification panel after clearing
    }, 200)
  } catch (error) {
    console.error('❌ NotificationFeed: Error clearing notifications:', error)
    
    // Force clear in case of error
    localStorage.setItem('streamvault_notifications', JSON.stringify([]))
    notifications.value = []
  }
}

// Save notifications to localStorage
const saveNotifications = (): void => {
  try {
    // First, ensure we only save valid notifications
    const validNotifications = notifications.value.filter(n => 
      n && typeof n === 'object' && n.id && n.type && n.timestamp
    );
    
    if (validNotifications.length !== notifications.value.length) {
      console.warn('⚠️ NotificationFeed: Filtered out invalid notifications before saving')
      // Update the notifications array to remove invalid items
      notifications.value = validNotifications
    }
    
    // Save to localStorage
    localStorage.setItem('streamvault_notifications', JSON.stringify(validNotifications))
    console.log('📝 NotificationFeed: Saved to localStorage:', validNotifications.length, 'notifications')
    
    // Get a sample to verify data integrity
    if (validNotifications.length > 0) {
      console.log('📝 NotificationFeed: Sample of saved notification:', validNotifications[0])
    }
  } catch (error) {
    console.error('❌ NotificationFeed: Error saving notifications to localStorage:', error)
  }
}

// Load notifications from localStorage
const loadNotifications = (): void => {
  const saved = localStorage.getItem('streamvault_notifications')
  if (saved) {
    try {
      const savedNotifications = JSON.parse(saved)
      if (Array.isArray(savedNotifications)) {
        // Only consider notifications with proper structure
        const validNotifications = savedNotifications.filter(n => 
          n && typeof n === 'object' && n.id && n.type && n.timestamp
        );
        
        if (validNotifications.length !== savedNotifications.length) {
          console.warn('⚠️ NotificationFeed: Found invalid notifications in localStorage, filtering them out')
        }
        
        notifications.value = validNotifications
        console.log('📝 NotificationFeed: Loaded from localStorage:', notifications.value.length, 'notifications')
        
        // Debug info - show what notifications we loaded
        if (notifications.value.length > 0) {
          console.log('📝 NotificationFeed: Loaded notifications:', notifications.value)
        }
      } else {
        console.error('Saved notifications is not an array:', saved)
        // Initialize with empty array if saved data is invalid
        notifications.value = []
      }
    } catch (e) {
      console.error('Failed to load notifications:', e)
      // Initialize with empty array if parsing fails
      notifications.value = []
    }
  } else {
    console.log('📝 NotificationFeed: No notifications in localStorage')
    notifications.value = []
  }
}

// Process new WebSocket messages
const processNewMessage = (message: any) => {
  console.log('🔔 NotificationFeed: Processing new WebSocket message:', message)
  
  // Check if message has required properties
  if (!message || !message.type) {
    console.error('❌ NotificationFeed: Invalid message format, missing type property:', message)
    return
  }
  
  // Only process certain notification types (excluding connection.status to prevent spam)
  const notificationTypes = [
    'stream.online', 
    'stream.offline',
    'channel.update',  // Standard Twitch notification type
    'stream.update',
    'recording.started',
    'recording.completed',
    'recording.failed',
    'test' // Special test notification type
  ]
  
  console.log('🔍 NotificationFeed: Checking message type:', message.type, 'against allowed types')
  
  if (notificationTypes.includes(message.type)) {
    console.log('✅ NotificationFeed: Message type accepted, adding notification:', message)
    
    try {
      // Try adding the notification
      addNotification(message)
      
      // Perform a verification check with a delay to ensure localStorage was updated
      setTimeout(() => {
        try {
          const savedNotifs = localStorage.getItem('streamvault_notifications')
          const savedCount = savedNotifs ? JSON.parse(savedNotifs).length : 0
          console.log(`🔒 NotificationFeed: Verification check - localStorage has ${savedCount} notifications`)
          
          // Force re-save if there's a mismatch (to ensure persistence)
          if (notifications.value.length !== savedCount) {
            console.warn('⚠️ NotificationFeed: Storage mismatch detected, forcing save')
            saveNotifications()
          }
        } catch (err) {
          console.error('❌ NotificationFeed: Error in verification check:', err)
        }
      }, 50)
    } catch (error) {
      console.error('❌ NotificationFeed: Error processing notification:', error)
    }
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
  
  // Prüfe, ob Benachrichtigungen vorhanden sind und ggf. warum nicht
  console.log('🔍 NotificationFeed: On mount - Notifications loaded from localStorage:', notifications.value.length)
  
  // Emit notifications-read when first mounted
  emit('notifications-read')
  
  // Watch for new WebSocket messages - improved approach
  watch(messages, (newMessages, oldMessages) => {
    console.log('📊 NotificationFeed: Messages watcher triggered', { 
      newMessagesLength: newMessages?.length, 
      oldMessagesLength: oldMessages?.length
    })
    
    // Don't process empty messages
    if (!newMessages || newMessages.length === 0) {
      console.log('📊 NotificationFeed: No messages to process')
      return
    }
    
    // Force refresh notifications from localStorage first to ensure we have the latest data
    try {
      loadNotifications();
      console.log('📊 NotificationFeed: Reloaded notifications from localStorage before processing')
    } catch (e) {
      console.error('❌ NotificationFeed: Error reloading notifications:', e)
    }
    
    // Only handle messages when we have new ones
    if (oldMessages && newMessages.length > oldMessages.length) {
      // Get only the new message
      const newMessage = newMessages[newMessages.length - 1]
      
      // Skip connection.status messages - they're not notifications
      if (newMessage.type === 'connection.status') {
        console.log('⏭️ NotificationFeed: Skipping connection.status message')
        return
      }
      
      console.log('🔄 NotificationFeed: Processing new message:', newMessage)
      
      try {
        // Add the notification directly (without the extra processNewMessage function)
        // This simplifies the code and avoids potential issues
        addNotification(newMessage)
        
        // Force reactivity update
        notifications.value = [...notifications.value]
      } catch (error) {
        console.error('❌ NotificationFeed: Error during message handling:', error)
      }
    } else {
      console.log('📊 NotificationFeed: No new messages to process')
    }
  }, { deep: true })
})
</script>

<style scoped>
.notification-feed {
  padding: 0;
  background: linear-gradient(135deg, 
    rgba(var(--background-darker-rgb, 31, 31, 35), 0.98) 0%,
    rgba(var(--background-card-rgb, 37, 37, 42), 0.95) 100%);
  border-radius: 16px;
  box-shadow: 
    0 20px 60px rgba(0, 0, 0, 0.4),
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  max-width: 420px;
  width: 100%;
  overflow: hidden;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(var(--border-color-rgb, 45, 45, 53), 0.8);
  position: absolute;
  top: 72px;
  right: 20px;
  z-index: 1000;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  animation: slideIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-20px) translateX(10px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) translateX(0) scale(1);
  }
}

.feed-header {
  padding: 24px 24px 16px;
  border-bottom: 1px solid rgba(var(--border-color-rgb, 45, 45, 53), 0.6);
  background: rgba(var(--background-darker-rgb, 31, 31, 35), 0.4);
  display: flex;
  justify-content: space-between;
  align-items: center;
  backdrop-filter: blur(8px);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon .icon-ring {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--primary-color), var(--primary-color-light, #4ade80));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 
    0 4px 12px rgba(var(--primary-color-rgb, 66, 184, 131), 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.bell-icon {
  font-size: 20px;
  filter: brightness(1.2);
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.section-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.025em;
}

.section-subtitle {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
}

.clear-all-btn {
  background: rgba(var(--danger-color-rgb, 239, 68, 68), 0.1);
  border: 1px solid rgba(var(--danger-color-rgb, 239, 68, 68), 0.2);
  color: var(--danger-color);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 8px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}

.clear-all-btn:hover {
  background: rgba(var(--danger-color-rgb, 239, 68, 68), 0.15);
  border-color: rgba(var(--danger-color-rgb, 239, 68, 68), 0.3);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(var(--danger-color-rgb, 239, 68, 68), 0.2);
}

.clear-icon {
  font-size: 0.75rem;
}

.no-notifications {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  min-height: 200px;
}

.empty-state {
  text-align: center;
  color: var(--text-secondary);
}

.empty-state .empty-icon {
  margin-bottom: 16px;
}

.empty-state .icon-circle {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: rgba(var(--background-card-rgb, 37, 37, 42), 0.8);
  border: 2px dashed rgba(var(--border-color-rgb, 45, 45, 53), 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  margin: 0 auto 16px;
}

.empty-state h3 {
  margin: 0 0 8px;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-state p {
  margin: 0;
  font-size: 0.875rem;
  opacity: 0.8;
}

.notification-list {
  padding: 8px;
  max-height: calc(85vh - 120px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(var(--primary-color-rgb, 66, 184, 131), 0.3) transparent;
}

.notification-list::-webkit-scrollbar {
  width: 6px;
}

.notification-list::-webkit-scrollbar-track {
  background: transparent;
}

.notification-list::-webkit-scrollbar-thumb {
  background: rgba(var(--primary-color-rgb, 66, 184, 131), 0.3);
  border-radius: 3px;
}

.notification-list::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--primary-color-rgb, 66, 184, 131), 0.5);
}

.notification-item {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  margin-bottom: 8px;
  background: rgba(var(--background-card-rgb, 37, 37, 42), 0.6);
  border-radius: 12px;
  position: relative;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(var(--border-color-rgb, 45, 45, 53), 0.4);
  overflow: hidden;
}

.notification-item:last-child {
  margin-bottom: 0;
}

.notification-item:hover {
  background: rgba(var(--background-card-rgb, 37, 37, 42), 0.9);
  border-color: rgba(var(--border-color-rgb, 45, 45, 53), 0.6);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.notification-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 0 2px 2px 0;
}

.notification-indicator.online {
  background: linear-gradient(180deg, var(--danger-color), #ff6b6b);
}

.notification-indicator.offline {
  background: linear-gradient(180deg, var(--text-secondary), #9ca3af);
}

.notification-indicator.update {
  background: linear-gradient(180deg, var(--primary-color), var(--primary-color-light, #4ade80));
}

.notification-indicator.recording {
  background: linear-gradient(180deg, var(--warning-color), #fbbf24);
}

.notification-indicator.success {
  background: linear-gradient(180deg, var(--success-color), #34d399);
}

.notification-indicator.error {
  background: linear-gradient(180deg, var(--danger-color), #f87171);
}

.notification-indicator.info {
  background: linear-gradient(180deg, var(--info-color, #0ea5e9), #38bdf8);
}

.notification-icon {
  flex-shrink: 0;
  margin-right: 16px;
  margin-left: 8px;
}

.icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.icon-wrapper.online {
  background: linear-gradient(135deg, rgba(255, 0, 0, 0.2), rgba(255, 107, 107, 0.15));
}

.icon-wrapper.offline {
  background: linear-gradient(135deg, rgba(150, 150, 150, 0.2), rgba(156, 163, 175, 0.15));
}

.icon-wrapper.update {
  background: linear-gradient(135deg, rgba(66, 184, 131, 0.2), rgba(74, 222, 128, 0.15));
}

.icon-wrapper.recording {
  background: linear-gradient(135deg, rgba(255, 165, 0, 0.2), rgba(251, 191, 36, 0.15));
}

.icon-wrapper.success {
  background: linear-gradient(135deg, rgba(66, 184, 131, 0.2), rgba(52, 211, 153, 0.15));
}

.icon-wrapper.error {
  background: linear-gradient(135deg, rgba(255, 0, 0, 0.2), rgba(248, 113, 113, 0.15));
}

.icon-wrapper.info {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(56, 189, 248, 0.15));
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}

.notification-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.notification-time {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  margin-left: 12px;
  font-weight: 500;
  opacity: 0.8;
}

.notification-message {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: 8px;
  word-break: break-word;
  line-height: 1.5;
}

.notification-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  padding: 4px 8px;
  background: rgba(var(--primary-color-rgb, 66, 184, 131), 0.1);
  border: 1px solid rgba(var(--primary-color-rgb, 66, 184, 131), 0.2);
  border-radius: 6px;
  color: var(--primary-color);
  font-weight: 500;
}

.tag-icon {
  font-size: 0.65rem;
}

.notification-dismiss {
  background: none;
  border: none;
  color: var(--text-secondary);
  opacity: 0.6;
  cursor: pointer;
  font-size: 1.2rem;
  line-height: 1;
  padding: 4px;
  margin: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.notification-dismiss:hover {
  opacity: 1;
  background: rgba(var(--danger-color-rgb, 239, 68, 68), 0.1);
  color: var(--danger-color);
  transform: scale(1.1);
}

.dismiss-icon {
  font-weight: 600;
}

/* Animation transitions */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(40px) scale(0.9);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(-40px) scale(0.9);
}

.notification-move {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
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
    max-height: calc(100vh - 120px);
  }
  
  .feed-header {
    padding: 20px 16px 16px;
  }
  
  .notification-list {
    padding: 4px;
  }
  
  .notification-item {
    padding: 12px;
  }
}

/* Dark mode enhancements */
@media (prefers-color-scheme: dark) {
  .notification-feed {
    box-shadow: 
      0 20px 60px rgba(0, 0, 0, 0.6),
      0 8px 32px rgba(0, 0, 0, 0.4),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
}
</style>
