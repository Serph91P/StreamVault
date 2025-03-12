<template>
  <form @submit.prevent="addStreamer" class="streamer-form">
    <div class="input-group">
      <input 
        type="text" 
        v-model="username" 
        :disabled="isLoading"
        placeholder="Enter Twitch username" 
        required
        class="input-field interactive-element"
      >
      <select 
        v-model="quality" 
        :disabled="isLoading"
        class="quality-select interactive-element"
      >
        <option value="best">Best</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
        <option value="audio_only">Audio Only</option>
      </select>
      <button type="submit" :disabled="isLoading" class="submit-button interactive-element">
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
const quality = ref('best') // Default quality
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
      },
      body: JSON.stringify({
        quality: quality.value
      })
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

<style scoped>
.quality-select {
  background: var(--background-dark, #18181b);
  color: var(--text-primary, #efeff1);
  border: 2px solid var(--border-color, #303034);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 16px;
  min-width: 120px;
  transition: all 0.2s ease;
}

.quality-select:focus {
  outline: none;
  border-color: var(--primary-color, #42b883);
  box-shadow: 0 0 0 2px rgba(66, 184, 131, 0.2);
}

.input-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

@media (min-width: 768px) {
  .input-group {
    flex-wrap: nowrap;
  }
  
  .quality-select {
    flex: 0 0 auto;
  }
  
  .input-field {
    flex: 1;
  }
  
  .submit-button {
    flex: 0 0 auto;
  }
}
</style>