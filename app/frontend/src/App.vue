<template>
  <div class="app">
    <!-- Desktop and tablet header -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-logo">StreamVault</h1>
        <nav class="main-nav">
          <router-link to="/" class="nav-link">Home</router-link>
          <router-link to="/streamers" class="nav-link">Streamers</router-link>
          <router-link to="/videos" class="nav-link">Videos</router-link>
          <router-link to="/add-streamer" class="nav-link">Add Streamer</router-link>
          <router-link to="/subscriptions" class="nav-link">Subscriptions</router-link>
          <router-link to="/settings" class="nav-link">Settings</router-link>
          <div class="notification-bell-container">
            <button @click="toggleNotifications" class="notification-bell" :class="{ 'has-unread': unreadCount > 0 }">
              <svg class="bell-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
              </svg>
              <span v-if="unreadCount > 0" class="notification-count">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
            </button>
          </div>
        </nav>
      </div>
    </header>    <!-- Notification overlay -->
    <div v-if="showNotifications" class="notification-overlay">
      <NotificationFeed 
        @notifications-read="markAsRead" 
        @close-panel="closeNotificationPanel"
        @clear-all="clearAllNotifications"
      />
    </div>
    
    <div class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
    
    <!-- Mobile navigation for better mobile experience -->
    <div class="mobile-nav-bottom">
      <router-link to="/" class="mobile-nav-item">
        <svg class="mobile-nav-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
          <polyline points="9 22 9 12 15 12 15 22"></polyline>
        </svg>
        <span>Home</span>
      </router-link>
      <router-link to="/streamers" class="mobile-nav-item">
        <svg class="mobile-nav-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-6"></path>
          <path d="M2 12h20"></path>
        </svg>
        <span>Streamers</span>
      </router-link>
      <router-link to="/videos" class="mobile-nav-item">
        <svg class="mobile-nav-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="23 7 16 12 23 17 23 7"></polygon>
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
        </svg>
        <span>Videos</span>
      </router-link>
      <router-link to="/add-streamer" class="mobile-nav-item">
        <svg class="mobile-nav-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="16"></line>
          <line x1="8" y1="12" x2="16" y2="12"></line>
        </svg>
        <span>Add</span>
      </router-link>
      <router-link to="/subscriptions" class="mobile-nav-item">
        <svg class="mobile-nav-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>
        <span>Subs</span>
      </router-link>
      <router-link to="/settings" class="mobile-nav-item">
        <svg class="mobile-nav-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
        <span>Settings</span>
      </router-link>
      <button @click="toggleNotifications" class="mobile-nav-item mobile-notification-btn">
        <svg class="mobile-nav-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>
        <span>Alerts</span>
        <span v-if="unreadCount > 0" class="mobile-notification-indicator"></span>
      </button>
    </div>
    
    <!-- PWA Install Prompt -->
    <PWAInstallPrompt />
  </div>
</template>

<script setup>
import NotificationFeed from '@/components/NotificationFeed.vue'
import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue'
import '@/styles/main.scss'
import { ref, onMounted, watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const showNotifications = ref(false)
const unreadCount = ref(0)
const lastReadTimestamp = ref(localStorage.getItem('lastReadTimestamp') || '0')

const { messages } = useWebSocket()

// WebSocket message processing - moved here so it runs even when notification panel is closed
const processWebSocketMessage = (message) => {
  console.log('🔥 App: Processing WebSocket message:', message)
  
  if (!message || !message.type) {
    console.log('❌ App: Invalid message')
    return
  }
  
  // Skip connection status messages
  if (message.type === 'connection.status') {
    console.log('⏭️ App: Skipping connection status')
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
    'test'
  ]
  
  if (validTypes.includes(message.type)) {
    console.log('✅ App: Valid message type, adding to localStorage')
    addNotificationToStorage(message)
  } else {
    console.log('❌ App: Invalid message type:', message.type)
  }
}

// Add notification to localStorage - similar to NotificationFeed logic
const addNotificationToStorage = (message) => {
  try {
    const id = message.data?.test_id || `${message.type}_${Date.now()}_${Math.random()}`
    
    const timestamp = message.data?.timestamp 
      ? new Date(parseInt(message.data.timestamp) || message.data.timestamp).toISOString()
      : new Date().toISOString()
    
    const streamer_username = message.data?.username || 
                             message.data?.streamer_name || 
                             'Unknown'
    
    const newNotification = {
      id,
      type: message.type,
      timestamp,
      streamer_username,
      data: message.data || {}
    }
    
    console.log('🔥 App: Created notification:', newNotification)
    
    // Get existing notifications
    let notifications = []
    try {
      const existing = localStorage.getItem('streamvault_notifications')
      if (existing) {
        notifications = JSON.parse(existing)
      }
    } catch (e) {
      notifications = []
    }
    
    // Add new notification to beginning
    notifications.unshift(newNotification)
    
    // Limit notifications
    if (notifications.length > 100) {
      notifications = notifications.slice(0, 100)
    }
    
    // Save back to localStorage
    localStorage.setItem('streamvault_notifications', JSON.stringify(notifications))
    
    console.log('💾 App: Saved notification to localStorage. Total notifications:', notifications.length)
    
    // Update unread count
    updateUnreadCountFromStorage()
    
    // Dispatch event for other components
    window.dispatchEvent(new CustomEvent('notificationsUpdated', {
      detail: { count: notifications.length }
    }))
    
  } catch (error) {
    console.error('❌ App: Error adding notification to localStorage:', error)
  }
}

// Track previous message count to detect new messages
let previousMessageCount = 0

// Watch for new WebSocket messages
watch(() => messages.value.length, (newLength) => {
  console.log('🔥 App: Message count changed to', newLength, 'from', previousMessageCount)
  
  if (newLength > previousMessageCount) {
    console.log('🔥 App: NEW MESSAGES DETECTED!')
    
    // Process only the new messages
    const newCount = newLength - previousMessageCount
    const messagesToProcess = messages.value.slice(-newCount)
    console.log('🔥 App: Processing', messagesToProcess.length, 'new messages')
    
    messagesToProcess.forEach((message, index) => {
      console.log(`🔥 App: Processing new message ${index + 1}:`, message)
      processWebSocketMessage(message)
    })
    
    previousMessageCount = newLength
  }
}, { immediate: false })

function toggleNotifications() {
  console.log('🔔 App: Toggling notifications panel')
  showNotifications.value = !showNotifications.value
  
  if (showNotifications.value) {
    console.log('🔔 Notifications panel opened')
    // Don't recalculate unread count when opening - let the notifications stay visible
  } else {
    console.log('🔔 Notifications panel closed')
  }
}

function markAsRead() {
  console.log('🔔 App: Marking all notifications as read')
  unreadCount.value = 0
  lastReadTimestamp.value = Date.now().toString()
  localStorage.setItem('lastReadTimestamp', lastReadTimestamp.value)
  console.log('🔔 App: Updated lastReadTimestamp in localStorage to:', lastReadTimestamp.value)
}

function clearAllNotifications() {
  console.log('🔔 App: Clearing all notifications - Event received from NotificationFeed')
  // Clear the notifications from localStorage (redundant but safe)
  localStorage.removeItem('streamvault_notifications')
  // Mark as read
  markAsRead()
  // Reset notification count
  notificationCount.value = 0
  // Dispatch event to notify other components
  window.dispatchEvent(new CustomEvent('notificationsUpdated', {
    detail: { count: 0 }
  }))
  console.log('🔔 App: All notifications cleared successfully')
}

function closeNotificationPanel() {
  if (showNotifications.value) {
    console.log('🔔 App: Closing notification panel')
    showNotifications.value = false
    markAsRead() // Mark as read when panel closes
  }
}

// Function to update unread count from localStorage
function updateUnreadCountFromStorage() {
  const notificationsStr = localStorage.getItem('streamvault_notifications')
  console.log('🔄 App: Checking localStorage for notifications')
  
  if (notificationsStr) {
    try {
      const notifications = JSON.parse(notificationsStr)
      console.log('🔄 App: Found notifications in localStorage:', notifications.length)
      
      if (Array.isArray(notifications)) {
        // Only count real notification types, not connection status
        const validNotificationTypes = [
          'stream.online', 
          'stream.offline', 
          'channel.update',
          'stream.update',
          'recording.started',
          'recording.completed',
          'recording.failed',
          'test' // Add test notification type to be counted
        ]
        
        const unread = notifications.filter(n => {
          const notifTimestamp = new Date(n.timestamp).getTime()
          const isValidType = validNotificationTypes.includes(n.type)
          const isUnread = notifTimestamp > parseInt(lastReadTimestamp.value)
          
          console.log(`🔄 App: Notification ${n.id} - Type: ${n.type}, Valid: ${isValidType}, Unread: ${isUnread}`)
          
          return isValidType && isUnread
        })
        
        unreadCount.value = unread.length
        console.log('🔢 App: Updated unread count to:', unreadCount.value, 'notifications')
        
        // Log the actual unread notifications for debugging
        if (unread.length > 0) {
          console.log('🔢 App: Unread notifications:', unread)
        }
      }
    } catch (e) {
      console.error('❌ App: Failed to parse notifications from localStorage', e)
    }
  } else {
    console.log('🔄 App: No notifications found in localStorage')
    unreadCount.value = 0
  }
}

// Update unread count from localStorage on mount
onMounted(() => {
  updateUnreadCountFromStorage()
  
  // Set initial message count
  previousMessageCount = messages.value.length
  console.log('🚀 App: Set initial message count to', previousMessageCount)
  
  // Process any existing WebSocket messages
  if (messages.value.length > 0) {
    console.log('🚀 App: Processing', messages.value.length, 'existing WebSocket messages')
    messages.value.forEach((message, index) => {
      console.log(`🚀 App: Processing existing message ${index + 1}:`, message)
      processWebSocketMessage(message)
    })
  }
  
  // Listen for clicks outside the notification area to close it
  document.addEventListener('click', (event) => {
    const notificationFeed = document.querySelector('.notification-feed')
    const notificationBell = document.querySelector('.notification-bell')

    if (showNotifications.value && 
        notificationFeed && 
        notificationBell && 
        !notificationFeed.contains(event.target) && 
        !notificationBell.contains(event.target)) {
      closeNotificationPanel() // Use the proper close function instead of just setting the value
    }
  })
  
  // Listen for localStorage changes to update count
  window.addEventListener('storage', (e) => {
    if (e.key === 'streamvault_notifications') {
      console.log('📦 App: localStorage notifications changed, updating count')
      updateUnreadCountFromStorage()
    }
  })
  
  // Listen for custom notifications updated event
  window.addEventListener('notificationsUpdated', () => {
    console.log('📦 App: Custom notificationsUpdated event received, updating count')
    updateUnreadCountFromStorage()
  })
})

// Track the previous message count to detect actual changes
const previousMessageCountApp = ref(0)

// Watch for new messages and update unread count
watch(messages, (newMessages) => {
  console.log('🔄 App: Messages watcher triggered. Messages count:', newMessages.length)
  
  if (!newMessages || newMessages.length === 0) return
  
  // Check if we have new messages
  if (newMessages.length > previousMessageCountApp.value) {
    // Get only the new messages since last check
    const newCount = newMessages.length - previousMessageCountApp.value
    const newMessagesToProcess = newMessages.slice(-newCount)
    
    // Update our counter for next time
    previousMessageCountApp.value = newMessages.length
    
    // Process each new message - but only count them, don't store them (NotificationFeed handles storage)
    newMessagesToProcess.forEach(newMessage => {
      console.log('🔄 App: Processing new message for counting:', newMessage)
      
      // Only count specific notification types (exclude connection.status to prevent false positives)
      const notificationTypes = [
        'stream.online', 
        'stream.offline', 
        'channel.update',  
        'stream.update',
        'recording.started',
        'recording.completed',
        'recording.failed',
        'test'  
      ]
      
      // Only increment if it's a valid notification type AND panel is not currently shown
      if (notificationTypes.includes(newMessage.type) && !showNotifications.value) {
        console.log('🔢 App: Valid notification type for counter:', newMessage.type)
        
        // Check if this notification has already been counted
        const notificationTimestamp = newMessage.data?.timestamp || Date.now()
        if (parseInt(notificationTimestamp) > parseInt(lastReadTimestamp.value)) {
          unreadCount.value++
          console.log('🔢 App: Unread count is now', unreadCount.value)
        } else {
          console.log('🔢 App: Notification timestamp older than last read, not incrementing count')
        }
      } else {
        console.log('⏭️ App: Skipping unread count for message type:', newMessage.type, 'or panel is open:', showNotifications.value)
      }
    })
  } else {
    console.log('🔄 App: No new messages detected')
  }
}, { deep: true, immediate: false }) // Don't process immediately
</script>

<style scoped>
/* Add the new styles for the notification bell */
.notification-bell-container {
  position: relative;
  margin-left: 10px;
}

.notification-bell {
  position: relative;
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 50%;
  color: var(--text-primary);
  transition: all 0.2s ease;
}

.notification-bell:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.notification-bell.has-unread .bell-icon {
  color: var(--primary-color);
  animation: bell-shake 1s cubic-bezier(.36,.07,.19,.97) both;
  transform-origin: top center;
}

@keyframes bell-shake {
  0% { transform: rotate(0); }
  15% { transform: rotate(5deg); }
  30% { transform: rotate(-5deg); }
  45% { transform: rotate(4deg); }
  60% { transform: rotate(-4deg); }
  75% { transform: rotate(2deg); }
  85% { transform: rotate(-2deg); }
  92% { transform: rotate(1deg); }
  100% { transform: rotate(0); }
}

.notification-count {
  position: absolute;
  top: -2px;
  right: -2px;
  background-color: var(--danger-color);
  color: white;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.mobile-notification-btn {
  position: relative;
}

.mobile-notification-btn {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  width: 100%;
  transition: all 0.2s ease;
}

.mobile-notification-btn:hover {
  color: var(--text-primary);
}

.mobile-notification-btn .mobile-nav-icon {
  margin-bottom: 4px;
  transition: transform 0.2s ease, stroke 0.2s ease;
  stroke: currentColor;
}

.mobile-notification-indicator {
  position: absolute;
  top: 2px;
  right: 5px;
  width: 8px;
  height: 8px;
  background-color: var(--danger-color);
  border-radius: 50%;
}

/* Notification overlay positioning */
.notification-overlay {
  position: fixed;
  top: 70px; /* Below the header */
  right: 20px;
  z-index: 1000;
  max-width: 400px;
  width: 90vw;
}

/* Mobile specific notification overlay */
@media (max-width: 767px) {
  .notification-overlay {
    top: 20px;
    right: 10px;
    left: 10px;
    width: auto;
    max-width: none;
  }
}

/* Ensure mobile navigation doesn't display on larger screens */
@media (min-width: 768px) {
  .mobile-nav-bottom {
    display: none;
  }
}
</style>