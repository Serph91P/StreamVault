<template>
  <div class="streamers-page">
    <div class="page-header">
      <div class="header-content">
        <h2>Your Streamers</h2>
        <p class="description">Manage your tracked streamers and their recordings</p>
      </div>
      <div class="header-actions">
        <router-link to="/" class="btn btn-secondary">Back to Dashboard</router-link>
        <router-link to="/add-streamer" class="btn btn-primary">Add Streamer</router-link>
      </div>
    </div>
    <StreamerList />
  </div>
</template>

<script setup lang="ts">
import StreamerList from '../components/StreamerList.vue';
</script>

<style scoped>
.streamers-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  gap: 2rem;
}

.header-content h2 {
  margin: 0 0 0.5rem 0;
  font-size: 2rem;
  color: var(--text-primary);
}

.description {
  color: var(--text-secondary);
  margin: 0;
  font-size: 1.1rem;
}

.header-actions {
  display: flex;
  gap: 1rem;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .streamers-page {
    padding: 1rem;
  }
  
  .page-header {
    flex-direction: column;
    gap: 1rem;
  }
  
  .header-actions {
    width: 100%;
  }
  
  .header-actions .btn {
    flex: 1;
  }
}
</style>
