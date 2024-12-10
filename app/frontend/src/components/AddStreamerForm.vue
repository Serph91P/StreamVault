<template>
  <div class="add-streamer-form">
    <form @submit.prevent="addStreamer">
      <input 
        type="text" 
        v-model="username" 
        placeholder="Enter streamer username"
        required
      >
      <button type="submit" :disabled="isSubmitting">Add Streamer</button>
    </form>
    <div v-if="feedback" :class="['feedback', feedback.type]">
      {{ feedback.message }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const username = ref('')
const isSubmitting = ref(false)
const feedback = ref(null)
const emit = defineEmits(['streamer-added'])

const addStreamer = async () => {
  try {
    isSubmitting.value = true
    feedback.value = null
    
    const formData = new FormData()
    formData.append('username', username.value)
    
    const response = await fetch('/api/streamers', {
      method: 'POST',
      body: formData
    })
    
    const data = await response.json()
    
    if (response.ok) {
      feedback.value = { type: 'success', message: data.message }
      username.value = ''
      emit('streamer-added')
    } else {
      feedback.value = { type: 'error', message: data.message }
    }
  } catch (error) {
    console.error('Error adding streamer:', error)
    feedback.value = { type: 'error', message: 'Failed to add streamer' }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.add-streamer-form {
  margin: 1rem 0;
}

form {
  display: flex;
  gap: 1rem;
}

input {
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

button {
  padding: 0.5rem 1rem;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:hover {
  background-color: #45a049;
}

.feedback {
  margin-top: 0.5rem;
  padding: 0.5rem;
  border-radius: 4px;
}

.feedback.success {
  background-color: #d4edda;
  color: #155724;
}

.feedback.error {
  background-color: #f8d7da;
  color: #721c24;
}

button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>