<script setup lang="ts">
import TheWelcome from '../components/TheWelcome.vue'
import StreamerList from '../components/StreamerList.vue'

const handleStreamerDeleted = async () => {
  // Refresh subscriptions or perform other necessary updates
}
</script>

<template>
  <main>
    <TheWelcome />
    <StreamerList @streamerDeleted="handleStreamerDeleted" />
  </main>
</template>
