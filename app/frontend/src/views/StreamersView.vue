<template>
  <div class="streamers-page">
    <h2>Your Streamers</h2>
    <StreamerList />
  </div>
</template>

<script setup lang="ts">
import StreamerList from '../components/StreamerList.vue';
</script>

<style scoped>
.streamers-page {
  max-width: 900px;
  margin: 2rem auto;
  padding: 2rem;
  background: var(--background-secondary);
  border-radius: var(--radius-lg);
  box-shadow: 0 2px 12px rgba(0,0,0,0.07);
}
.streamers-page h2 {
  margin-bottom: 1.5rem;
}
</style>
