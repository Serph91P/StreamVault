<script setup lang="ts">
import TheWelcome from '../components/TheWelcome.vue'
import StreamerList from '../components/StreamerList.vue'

const handleStreamerDeleted = async () => {
  // Refresh subscriptions or perform other necessary updates
}
</script>

<template>
  <div class="home-view">
    <TheWelcome />
    <StreamerList @streamerDeleted="handleStreamerDeleted" />
  </div>
</template>
