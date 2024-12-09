<template>
  <div class="notification-feed">
    <TransitionGroup name="notification">
      <div v-for="notification in notifications" 
           :key="notification.id" 
           class="notification-item">
        {{ notification.message }}
        <span class="notification-time">{{ formatTime(notification.timestamp) }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const notifications = ref([])
const { messages } = useWebSocket()

messages.value.forEach(msg => {
  notifications.value.unshift({
    id: Date.now(),
    message: msg,
    timestamp: new Date()
  })
})

function formatTime(date) {
  return new Date(date).toLocaleTimeString()
}
</script>
