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
    const response = await fetch(`/api/streamers/${username.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
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
.streamer-form {
  width: 100%;
  max-width: 600px;
  margin: 0 auto;
}

.input-group {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}

.input-field {
  flex: 1;
  background: #18181b;
  border: 2px solid #3a3a3d;
  color: #efeff1;
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 1rem;
  transition: all 0.2s ease;
}

.input-field:focus {
  outline: none;
  border-color: #9147ff;
  box-shadow: 0 0 0 2px rgba(145, 71, 255, 0.2);
}

.input-field::placeholder {
  color: #5c5c5e;
}

.submit-button {
  background: #9147ff;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.submit-button:hover {
  background: #772ce8;
}

.submit-button:disabled {
  background: #392e5c;
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

.status-message {
  text-align: center;
  color: #adadb8;
  margin-top: 1rem;
  font-size: 0.9rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>