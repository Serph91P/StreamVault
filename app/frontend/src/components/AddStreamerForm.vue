<template>
  <form @submit.prevent="addStreamer" class="streamer-form">
    <input 
      type="text" 
      v-model="username" 
      :disabled="isLoading"
      placeholder="Streamer Username" 
      required
    >
    <button type="submit" :disabled="isLoading">
      <span v-if="isLoading" class="loader"></span>
      {{ isLoading ? 'Adding Streamer...' : 'Add Streamer' }}
    </button>
    <div v-if="isLoading" class="status-message">
      {{ statusMessage }}
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'

const username = ref('')
const isLoading = ref(false)
const statusMessage = ref('')

const addStreamer = async () => {
  isLoading.value = true
  statusMessage.value = 'Checking Twitch API...'
  
  try {
    const response = await fetch('/api/streamers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value })
    })
    
    statusMessage.value = 'Setting up EventSub notifications...'
    const data = await response.json()
    
    if (response.ok) {
      username.value = ''
    }
  } catch (error) {
    console.error('Error:', error)
  } finally {
    isLoading.value = false
    statusMessage.value = ''
  }
}
</script>

<style scoped>
.loader {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #6441a5;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.status-message {
  margin-top: 10px;
  color: #6441a5;
  font-size: 0.9em;
}

.streamer-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>