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
      <NotificationFeed v-if="showNotifications" @notifications-read="markAsRead" />
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
  showNotifications.value = !showNotifications.value
  if (showNotifications.value) {
    markAsRead()
  }
}

function markAsRead() {
  unreadCount.value = 0
  lastReadTimestamp.value = Date.now().toString()
  localStorage.setItem('lastReadTimestamp', lastReadTimestamp.value)
}

// Update unread count from localStorage on mount
onMounted(() => {
  const notificationsStr = localStorage.getItem('streamvault_notifications')
  if (notificationsStr) {
    try {
      const notifications = JSON.parse(notificationsStr)
      if (Array.isArray(notifications)) {
        const unread = notifications.filter(n => {
          const notifTimestamp = new Date(n.timestamp).getTime()
          return notifTimestamp > parseInt(lastReadTimestamp.value)
        })
        unreadCount.value = unread.length
      }
    } catch (e) {
      console.error('Failed to parse notifications from localStorage', e)
    }
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

// Watch for new messages and update unread count
watch(messages, (newMessages, oldMessages) => {
  if (!newMessages || newMessages.length === 0) return
  
  if (oldMessages && newMessages.length > oldMessages.length) {
    const newMessage = newMessages[newMessages.length - 1]
    const notificationTypes = [
      'stream.online', 
      'stream.offline', 
      'channel.update',
      'stream.update',
      'recording.started',
      'recording.completed',
      'recording.failed'
    ]
    
    if (notificationTypes.includes(newMessage.type)) {
      unreadCount.value++
    }
  }
}, { deep: true })
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