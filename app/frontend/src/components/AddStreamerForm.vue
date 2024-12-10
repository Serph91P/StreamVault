<template>
  <div class="add-streamer-form">
    <form @submit.prevent="addStreamer">
      <input 
        type="text" 
        v-model="username" 
        placeholder="Enter streamer username"
        required
      >
      <button type="submit">Add Streamer</button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const username = ref('')
const emit = defineEmits(['streamer-added'])

const addStreamer = async () => {
  try {
    const response = await fetch('/api/streamers', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: `username=${encodeURIComponent(username.value)}`
    })
    
    if (response.ok) {
      emit('streamer-added')
      username.value = ''
    }
  } catch (error) {
    console.error('Error adding streamer:', error)
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
</style>