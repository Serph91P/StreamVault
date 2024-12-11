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
.add-streamer-form {
  display: flex;
  gap: 12px;
  margin: 20px 0;
}

.input-field {
  background: #242424;
  border: 1px solid #383838;
  color: #fff;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 1rem;
  transition: border-color 0.2s;
}

.input-field:focus {
  outline: none;
  border-color: #6441a5;
}

.input-field::placeholder {
  color: #666;
}

.add-button {
  background: #6441a5;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.add-button:hover {
  background: #7d5bbe;
}

.add-button:disabled {
  background: #4a3178;
  cursor: not-allowed;
}

.loader {
  width: 16px;
  height: 16px;
  border: 2px solid #fff;
  border-top: 2px solid transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>