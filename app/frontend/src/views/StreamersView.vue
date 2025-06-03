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

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: var(--radius-md);
  text-decoration: none;
  font-weight: 600;
  transition: all 0.2s ease;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover {
  background: var(--primary-color-hover);
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--background-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--background-hover);
  transform: translateY(-1px);
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
    justify-content: stretch;
  }
  
  .btn {
    flex: 1;
    justify-content: center;
  }
}
</style>
