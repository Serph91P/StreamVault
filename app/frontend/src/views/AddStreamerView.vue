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
