<template>
  <form @submit.prevent="addStreamer" class="streamer-form">
    <div class="input-group">
      <input 
        type="text" 
        v-model="username" 
        :disabled="isLoading"
        placeholder="Enter Twitch username" 
        required
        class="input-field"
      >
      <button type="submit" :disabled="isLoading" class="submit-button">
        <span v-if="isLoading" class="loader"></span>
        {{ isLoading ? 'Adding...' : 'Add Streamer' }}
      </button>
    </div>
    <div v-if="statusMessage" class="status-message" :class="{ error: hasError }">
      {{ statusMessage }}
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'

const username = ref('')
const isLoading = ref(false)
const statusMessage = ref('')
const hasError = ref(false)

const addStreamer = async () => {
  if (!username.value.trim()) return

  isLoading.value = true
  statusMessage.value = 'Adding streamer...'
  hasError.value = false

  try {
    const cleanUsername = username.value.trim().toLowerCase()
    
    const response = await fetch(`/api/streamers/${cleanUsername}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    const data = await response.json()
    
    if (response.ok) {
      statusMessage.value = 'Streamer added successfully!'
      username.value = ''
      emit('streamer-added')
    } else {
      hasError.value = true
      statusMessage.value = data.message || 'Failed to add streamer'
    }
  } catch (error) {
    hasError.value = true
    statusMessage.value = 'Error connecting to server'
    console.error('Error:', error)
  } finally {
    isLoading.value = false
  }
}

const emit = defineEmits(['streamer-added'])
</script>