<template>
  <div class="notification-feed">
    <TransitionGroup name="notification">
      <div v-for="notification in notifications" 
           :key="notification.id" 
           class="notification-item interactive-element"
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

const NOTIFICATION_TIMEOUT = 3000

function formatNotificationMessage(message) {
  switch (message.type) {
    case 'connection.status':
      return message.data.message
    case 'channel.update':
      return `${message.data.streamer_name} updated stream: ${message.data.title}`
    case 'stream.online':
      return `${message.data.streamer_name} is now live!`
    case 'stream.offline':
      return `${message.data.streamer_name} went offline`
    default:
      return message.data?.message || message.message
  }
}

watch(messages, (newMessages) => {
  if (newMessages.length > 0) {
    const message = newMessages[newMessages.length - 1]
    const notification = {
      id: Date.now(),
      message: formatNotificationMessage(message),
      type: message.type,
      timestamp: new Date()
    }
    
    notifications.value.unshift(notification)
    
    setTimeout(() => {
      notifications.value = notifications.value.filter(n => n.id !== notification.id)
    }, NOTIFICATION_TIMEOUT)
  }
}, { deep: true })

function formatTime(date) {
  return new Date(date).toLocaleTimeString()
}
</script>
