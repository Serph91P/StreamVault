<template>
  <div class="streamer-form">
    <div class="form-group">
      <input 
        class="input-field"
        v-model="username" 
        placeholder="Enter streamer username" 
      />
    </div>
    <button @click="addStreamer" class="btn btn-primary">Add Streamer</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const username = ref('')
const emit = defineEmits(['streamer-added'])

async function addStreamer() {
  if (!username.value.trim()) return
  
  try {
    const response = await fetch(`/api/streamers/${username.value}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    if (data.success) {
      emit('streamer-added');
      username.value = '';
    }
  } catch (error) {
    console.error('Error adding streamer:', error);
  }
}
</script>
