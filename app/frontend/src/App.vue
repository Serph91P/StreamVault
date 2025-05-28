<template>
  <div class="app">
    <!-- Desktop and tablet header -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-logo">StreamVault</h1>
        <nav class="main-nav">
          <router-link to="/" class="nav-link">Home</router-link>
          <router-link to="/streamers" class="nav-link">Streamers</router-link>
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
    </header>
    
    <div class="main-content">
      <NotificationFeed 
        v-if="showNotifications" 
        @notifications-read="markAsRead" 
        @close-panel="closeNotificationPanel"
      />
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
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="8" y1="12" x2="16" y2="12"></line>
        </svg>
        <span>Streamers</span>
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
  </div>
</template>

<script setup>
import NotificationFeed from '@/components/NotificationFeed.vue'
import '@/styles/main.scss'
import { ref, onMounted, watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const showNotifications = ref(false)
const unreadCount = ref(0)
const lastReadTimestamp = ref(localStorage.getItem('lastReadTimestamp') || '0')

const { messages } = useWebSocket()

function toggleNotifications() {
  // Check localStorage for debugging
  const savedNotifications = localStorage.getItem('streamvault_notifications')
  console.log('📂 LocalStorage notifications check:', savedNotifications)
  
  showNotifications.value = !showNotifications.value
  if (showNotifications.value) {
    console.log('🔔 Notifications panel opened, marking as read')
    markAsRead()
  } else {
    console.log('🔔 Notifications panel closed')
  }
}

function markAsRead() {
  console.log('🔔 App: Marking all notifications as read')
  unreadCount.value = 0
  lastReadTimestamp.value = Date.now().toString()
  localStorage.setItem('lastReadTimestamp', lastReadTimestamp.value)
  
  // Verify that we actually updated localStorage
  const saved = localStorage.getItem('lastReadTimestamp')
  console.log('🔔 App: Updated lastReadTimestamp in localStorage to:', saved)
}

function closeNotificationPanel() {
  // Only close if currently open to prevent unnecessary re-renders
  if (showNotifications.value) {
    console.log('🔔 App: Closing notification panel')
    showNotifications.value = false
    
    // Re-check unread count when closing panel
    // This ensures we have the correct count in case notifications were added while panel was open
    const notificationsStr = localStorage.getItem('streamvault_notifications')
    if (notificationsStr) {
      try {
        const notifications = JSON.parse(notificationsStr)
        console.log('🔄 App: Re-checking unread count on panel close, found:', notifications.length, 'notifications')
      } catch (e) {
        console.error('❌ App: Error parsing notifications during panel close:', e)
      }
    }
  }
}

// Update unread count from localStorage on mount
onMounted(() => {
  const notificationsStr = localStorage.getItem('streamvault_notifications')
  console.log('🔄 App: Checking localStorage for notifications on startup')
  
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
      showNotifications.value = false
    }
  })
})

// Track the previous message count to detect actual changes
const previousMessageCountApp = ref(0);

// Watch for new messages and update unread count
watch(messages, (newMessages) => {
  console.log('🔄 App: Messages watcher triggered. Messages count:', newMessages.length);
  
  if (!newMessages || newMessages.length === 0) return;
  
  // Check if we have new messages
  if (newMessages.length > previousMessageCountApp.value) {
    // Get only the new messages since last check
    const newCount = newMessages.length - previousMessageCountApp.value;
    const newMessagesToProcess = newMessages.slice(-newCount);
    
    // Update our counter for next time
    previousMessageCountApp.value = newMessages.length;
    
    // Process each new message
    newMessagesToProcess.forEach(newMessage => {
      console.log('🔄 App: Processing new message:', newMessage);
      
      // Only count specific notification types (exclude connection.status to prevent false positives)
      const notificationTypes = [
        'stream.online', 
        'stream.offline', 
        'channel.update',  // Standard Twitch notification type
        'stream.update',
        'recording.started',
        'recording.completed',
        'recording.failed',
        'test'  // Our custom test notification type
      ];
      
      // Only increment if it's a valid notification type AND panel is not currently shown
      if (notificationTypes.includes(newMessage.type) && !showNotifications.value) {
        console.log('🔢 App: Valid notification type for counter:', newMessage.type);
        
        // Check if this notification has already been counted
        const notificationTimestamp = newMessage.data?.timestamp || Date.now();
        if (parseInt(notificationTimestamp) > parseInt(lastReadTimestamp.value)) {
          unreadCount.value++;
          console.log('🔢 App: Unread count is now', unreadCount.value);
        } else {
          console.log('🔢 App: Notification timestamp older than last read, not incrementing count');
        }
      } else {
        console.log('⏭️ App: Skipping unread count for message type:', newMessage.type, 'or panel is open:', showNotifications.value);
      }
    });
  } else {
    console.log('🔄 App: No new messages detected');
  }
}, { deep: true, immediate: true });
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

.mobile-notification-indicator {
  position: absolute;
  top: 2px;
  right: 5px;
  width: 8px;
  height: 8px;
  background-color: var(--danger-color);
  border-radius: 50%;
}

/* Ensure mobile navigation doesn't display on larger screens */
@media (min-width: 768px) {
  .mobile-nav-bottom {
    display: none;
  }
}
</style>