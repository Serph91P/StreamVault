<script setup lang="ts">
import TheWelcome from '../components/TheWelcome.vue'
import StreamerList from '../components/StreamerList.vue'

const handleStreamerDeleted = async () => {
  // Refresh subscriptions or perform other necessary updates
}
</script>

<template>
  <div class="home-view">
    <div class="container">
      <TheWelcome />
      
      <div class="content-section">
        <div class="page-header">
          <h2>Your Streamers</h2>
          <p class="description">Manage your tracked streamers and their recordings</p>
        </div>
        
        <StreamerList @streamerDeleted="handleStreamerDeleted" />
      </div>
    </div>
  </div>
</template>
