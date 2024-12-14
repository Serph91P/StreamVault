<template>
  <div class="add-streamer-page">
    <h2>Add New Streamer</h2>
    <p class="description">Add your favorite Twitch streamers to get notifications when they go live.</p>
    <AddStreamerForm @streamer-added="handleStreamerAdded" />
  </div>
</template>

<script setup>
import AddStreamerForm from '@/components/AddStreamerForm.vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const handleStreamerAdded = () => {
  router.push('/')
}
</script>

<style scoped>
.add-streamer-page {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
  background: #1f1f23;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

h2 {
  color: #efeff1;
  margin-bottom: 1rem;
  font-size: 1.8rem;
}

.description {
  color: #adadb8;
  margin-bottom: 2rem;
  font-size: 1.1rem;
}
</style>
