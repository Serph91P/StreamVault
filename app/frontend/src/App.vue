<template>
  <div class="app">
    <!-- Show header and navigation ONLY on authenticated pages -->
    <template v-if="!isAuthPage">
      <!-- Simplified Header (no navigation - moved to BottomNav/SidebarNav) -->
      <header class="app-header">
        <div class="header-content">
          <router-link to="/" class="app-logo">StreamVault</router-link>
          
          <div class="header-right">
            <!-- Background Queue Monitor -->
            <BackgroundQueueMonitor />
            
            <div class="nav-actions">
              <div class="notification-bell-container">
                <button @click="toggleNotifications" class="notification-bell" :class="{ 'has-unread': unreadCount > 0 }">
                  <svg class="bell-icon">
                    <use href="#icon-bell" />
                  </svg>
                  <span v-if="unreadCount > 0" class="notification-count">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
                </button>
              </div>
              <!-- Theme Toggle -->
              <ThemeToggle />
              <button @click="logout" class="logout-btn">
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>    
      <!-- Notification overlay -->
      <div v-if="showNotifications" class="notification-overlay">
        <NotificationFeed 
          @notifications-read="markAsRead" 
          @close-panel="closeNotificationPanel"
          @clear-all="clearAllNotifications"
        />
      </div>
    </template>
    
    <!-- Toast notifications (always visible) -->
    <ToastNotification 
      v-for="toast in activeToasts" 
      :key="toast.id"
      :message="toast.message"
      :type="toast.type"
      :duration="toast.duration"
      :data="toast.data"
      @dismiss="removeToast"
    />
    
    <!-- Navigation Wrapper with Bottom Nav + Sidebar (only on authenticated pages) -->
    <NavigationWrapper v-if="!isAuthPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </NavigationWrapper>
    
    <!-- Auth pages without navigation -->
    <router-view v-else v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    
    <!-- PWA Install Prompt -->
    <PWAInstallPrompt />
  </div>
</template>

<script setup>
import NotificationFeed from '@/components/NotificationFeed.vue'
import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue'
import BackgroundQueueMonitor from '@/components/BackgroundQueueMonitor.vue'
import ToastNotification from '@/components/ToastNotification.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import NavigationWrapper from '@/components/navigation/NavigationWrapper.vue'
import '@/styles/main.scss'
import { ref, onMounted, watch, provide, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAuth } from '@/composables/useAuth'
import { useSystemAndRecordingStatus } from '@/composables/useSystemAndRecordingStatus'
import { useTheme } from '@/composables/useTheme'

// Initialize theme
const { initializeTheme } = useTheme()
initializeTheme()

// Check if current route is an auth page
const route = useRoute()
const isAuthPage = computed(() => {
  const authPaths = ['/auth/login', '/auth/setup', '/welcome']
  return authPaths.includes(route.path)
})

// Provide hybrid status globally
const hybridStatus = useSystemAndRecordingStatus()
provide('hybridStatus', hybridStatus)

// Initialize hybrid status system
onMounted(() => {
  // Start the hybrid status system
  hybridStatus.fetchAllStatus()
})

const showNotifications = ref(false)
const unreadCount = ref(0)
const lastReadTimestamp = ref(localStorage.getItem('lastReadTimestamp') || '0')

// Toast notification management
const activeToasts = ref([])

const { messages } = useWebSocket()
const { logout: authLogout, checkStoredAuth } = useAuth()

// PWA-compatible logout function
async function logout() {
  if (confirm('Are you sure you want to logout?')) {
    await authLogout()
  }
}

// Toast notification functions
function addToast(message, type = 'info', duration = 5000, data = null) {
  const id = `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  
  const toast = {
    id,
    message,
    type,
    duration,
    data
  }
  
  activeToasts.value.push(toast)
  
  // Auto-remove after duration (unless duration is 0 for persistent toasts)
  if (duration > 0) {
    setTimeout(() => {
      removeToast(id)
    }, duration)
  }
}

function removeToast(toastId) {
  const index = activeToasts.value.findIndex(toast => toast.id === toastId)
  if (index > -1) {
    activeToasts.value.splice(index, 1)
  }
}

// Process toast notifications from WebSocket
function processToastNotification(message) {
  if (message.type === 'toast_notification') {
    const { 
      message: toastMessage, 
      type = 'info', 
      duration = 5000, 
      data = null 
    } = message.data || {}
    
    if (toastMessage) {
      addToast(toastMessage, type, duration, data)
    }
  }
}

// PWA AUTH FIX: Check stored auth on app start
onMounted(async () => {
  await checkStoredAuth()
})

// WebSocket message processing - moved here so it runs even when notification panel is closed
const processWebSocketMessage = (message) => {
  if (!message || !message.type) {
    return
  }
  
  // Process toast notifications first
  if (message.type === 'toast_notification') {
    processToastNotification(message)
    return // Don't store toast notifications in regular notification history
  }
  
  // Skip connection status messages
  if (message.type === 'connection.status') {
    return
  }
  
  // Valid notification types for history
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
    addNotificationToStorage(message)
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
  if (newLength > previousMessageCount) {
    // Process only the new messages
    const newCount = newLength - previousMessageCount
    const messagesToProcess = messages.value.slice(-newCount)
    
    messagesToProcess.forEach((message, index) => {
      processWebSocketMessage(message)
    })
    
    previousMessageCount = newLength
  }
}, { immediate: false })

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
}

function markAsRead() {
  unreadCount.value = 0
  lastReadTimestamp.value = Date.now().toString()
  localStorage.setItem('lastReadTimestamp', lastReadTimestamp.value)
}

function clearAllNotifications() {
  // Clear the notifications from localStorage (redundant but safe)
  localStorage.removeItem('streamvault_notifications')
  // Mark as read
  markAsRead()
  // Reset notification count
  unreadCount.value = 0
  // Dispatch event to notify other components
  window.dispatchEvent(new CustomEvent('notificationsUpdated', {
    detail: { count: 0 }
  }))
}

function closeNotificationPanel() {
  if (showNotifications.value) {
    showNotifications.value = false
    markAsRead() // Mark as read when panel closes
  }
}

// Function to update unread count from localStorage
function updateUnreadCountFromStorage() {
  const notificationsStr = localStorage.getItem('streamvault_notifications')
  
  if (notificationsStr) {
    try {
      const notifications = JSON.parse(notificationsStr)
      
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
          
          return isValidType && isUnread
        })
        
        unreadCount.value = unread.length
      }
    } catch (e) {
      console.error('❌ App: Failed to parse notifications from localStorage', e)
    }
  } else {
    unreadCount.value = 0
  }
}

// Update unread count from localStorage on mount
onMounted(() => {
  updateUnreadCountFromStorage()
  
  // Set initial message count
  previousMessageCount = messages.value.length
  
  // Process any existing WebSocket messages
  if (messages.value.length > 0) {
    messages.value.forEach((message, index) => {
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
      updateUnreadCountFromStorage()
    }
  })
  
  // Listen for custom notifications updated event
  window.addEventListener('notificationsUpdated', () => {
    updateUnreadCountFromStorage()
  })
})

// Track the previous message count to detect actual changes
const previousMessageCountApp = ref(0)

// Watch for new messages and update unread count
watch(messages, (newMessages) => {
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
        // Check if this notification has already been counted
        const notificationTimestamp = newMessage.data?.timestamp || Date.now()
        if (parseInt(notificationTimestamp) > parseInt(lastReadTimestamp.value)) {
          unreadCount.value++
        }
      }
    })
  }
}, { deep: true, immediate: false }) // Don't process immediately
</script>

<style scoped>
/* Modern Header Styles (Phase 1 Enhanced) */
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  width: 100%;
  height: 64px;
  z-index: 1100;

  /* Glassmorphism effect */
  background: rgba(var(--background-card-rgb), 0.85);
  backdrop-filter: blur(24px) saturate(180%);
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);

  /* Smooth theme transitions */
  transition: background-color 300ms var(--vue-ease-out),
              border-color 300ms var(--vue-ease-out);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  width: 100%;
  max-width: 100%;
  padding: 0 var(--spacing-6, 1.5rem);
  gap: var(--spacing-4, 1rem);
}

.app-logo {
  font-size: var(--text-xl, 1.25rem);
  font-weight: var(--font-bold, 700);
  color: var(--primary-color);
  text-decoration: none;
  line-height: 1;

  /* Smooth transition */
  transition: color var(--duration-200, 200ms) var(--vue-ease-out);

  &:hover {
    color: var(--accent-color);
  }

  /* Focus-visible for keyboard navigation */
  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 4px;
    border-radius: var(--radius-sm, 4px);
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-3, 0.75rem);
  height: 100%;
}

/* Navigation actions styles */
.nav-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-3, 0.75rem);
  height: 100%;
}

.notification-bell-container {
  position: relative;
}

.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2, 0.5rem);
  min-height: 44px;
  padding: var(--spacing-2, 0.5rem) var(--spacing-4, 1rem);

  /* Colors */
  background: var(--danger-color);
  color: white;
  border: none;
  border-radius: var(--radius-lg, 12px);

  /* Typography */
  font-size: var(--text-sm, 0.875rem);
  font-weight: var(--font-medium, 500);
  line-height: 1;

  /* Interaction */
  cursor: pointer;
  transition: all var(--duration-200, 200ms) var(--vue-ease-out);

  &:hover {
    background: var(--danger-600, #dc2626);
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  &:active {
    transform: translateY(0);
    box-shadow: var(--shadow-sm);
  }

  &:focus-visible {
    outline: 2px solid var(--danger-color);
    outline-offset: 2px;
  }
}

.notification-bell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;

  /* Touch-friendly sizing */
  min-width: 44px;
  min-height: 44px;
  width: 44px;
  height: 44px;
  padding: var(--spacing-2, 8px);

  /* Style */
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--text-primary);

  /* Interaction */
  cursor: pointer;
  transition: all var(--duration-200, 200ms) var(--vue-ease-out);

  .bell-icon {
    width: 24px;
    height: 24px;
    stroke: currentColor;
    fill: none;
    transition: transform var(--duration-200, 200ms) var(--vue-ease-out);
  }

  &:hover {
    background-color: rgba(var(--primary-500-rgb), 0.1);
    color: var(--primary-color);

    .bell-icon {
      transform: scale(1.1);
    }
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.notification-bell.has-unread .bell-icon {
  color: var(--primary-500);
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
  top: 4px;
  right: 4px;
  background-color: var(--danger-500);
  color: white;
  border-radius: 50%;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
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
  
  .header-content {
    padding: 0 1rem;
  }
  
  .app-logo {
    font-size: 1.25rem;
  }
}
</style>
