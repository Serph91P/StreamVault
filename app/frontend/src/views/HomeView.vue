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
      <div class="status-box">
        <h2>Dashboard</h2>
        <p>Welcome back to StreamVault! Here you can see the current status of your streamers and recordings.</p>
        <!-- You can add more stats here, e.g. number of streamers, last recording, etc. -->
      </div>
      
      <TheWelcome />
      
      <section class="content-section">
        <div class="page-header">
          <h2>Your Streamers</h2>
          <p class="description">Manage your tracked streamers and their recordings</p>
        </div>
        
        <StreamerList @streamer-deleted="handleStreamerDeleted" />
      </section>
    </div>
  </div>
</template>

<style scoped>
.status-box {
  background: var(--background-secondary);
  border-radius: var(--radius-md);
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  padding: 1.5rem 2rem;
  margin-bottom: 2rem;
  text-align: center;
}
.status-box h2 {
  margin-bottom: 0.5rem;
}
</style>
