<template>
  <div class="notification-feed">
    <TransitionGroup name="notification">
      <div v-for="notification in notifications" 
           :key="notification.id" 
           class="notification-item"
           :class="notification.type">
        <div class="notification-content">
          {{ notification.message }}
        </div>
        <span class="notification-time">{{ formatTime(notification.timestamp) }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const notifications = ref([])
const { messages } = useWebSocket()

const NOTIFICATION_TIMEOUT = 5000 // 5 seconds

watch(messages, (newMessages) => {
  if (newMessages.length > 0) {
    const message = newMessages[newMessages.length - 1]
    const notification = {
      id: Date.now(),
      message: message.data?.message || message.message,
      type: message.type,
      timestamp: new Date()
    }
    
    notifications.value.unshift(notification)
    
    // Remove notification after timeout
    setTimeout(() => {
      notifications.value = notifications.value.filter(n => n.id !== notification.id)
    }, NOTIFICATION_TIMEOUT)
  }
}, { deep: true })

function formatTime(date) {
  return new Date(date).toLocaleTimeString()
}
</script>
<style scoped>
.notification-feed {
  position: fixed;
  top: 80px;
  right: 20px;
  width: 300px;
  z-index: 1000;
}

.notification-item {
  background: #2f2f2f;
  color: white;
  padding: 1rem;
  margin-bottom: 0.5rem;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.notification-item.success {
  background: #28a745;
}

.notification-item.error {
  background: #dc3545;
}

.notification-time {
  font-size: 0.8em;
  color: rgba(255,255,255,0.7);
}

.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from,
.notification-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
