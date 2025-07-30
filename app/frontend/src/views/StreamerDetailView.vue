<template>
  <div class="streamer-detail-view">
    <div class="streamer-detail-container">
      <div class="page-header">
        <div class="header-left">
          <router-link to="/streamers" class="back-button">
            <i class="fas fa-arrow-left"></i>
            Back to Streamers
          </router-link>
          <div class="header-info" v-if="streamerName">
            <h1>{{ streamerName }}</h1>
            <p class="header-subtitle">Stream History & Recording Management</p>
          </div>
        </div>
        
        <!-- Add Force Recording Button here as well -->
        <div class="header-actions">
          <button 
            @click="forceStartRecording(Number(streamerId))" 
            class="btn btn-success"
            :disabled="forceRecordingStreamerId === Number(streamerId)"
            title="Force Start Recording - Checks if streamer is currently live and starts recording automatically"
            aria-label="Force start recording for this streamer - validates live status via API and begins recording if online"
          >
            <span v-if="forceRecordingStreamerId === Number(streamerId)">
              <i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Checking & Starting...
            </span>
            <span v-else>
              <i class="fas fa-record-vinyl" aria-hidden="true"></i> Force Record Streamer
            </span>
          </button>
        </div>
      </div>
      
      <div class="streamer-content">
        <StreamList :hide-header="true" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import StreamList from '@/components/StreamList.vue'
import { useForceRecording } from '@/composables/useForceRecording'

const route = useRoute()
const streamerName = computed(() => route.query.name as string)
const streamerId = computed(() => route.params.id as string)

// Use Force Recording Composable
const { forceRecordingStreamerId, forceStartRecording } = useForceRecording()
</script>

<style scoped>
.streamer-detail-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.streamer-detail-container {
  background: var(--background-darker, #1f1f23);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color, #333);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
}

/* Header Actions Styling */
.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header-actions .btn {
  font-weight: 600;
  border: 2px solid transparent;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header-actions .btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.header-actions .btn-success {
  background: #22c55e;
  color: white;
  border-color: #16a34a;
}

.header-actions .btn-success:hover:not(:disabled) {
  background: #16a34a;
  border-color: #15803d;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--border-radius);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--background-dark, #18181b);
  color: var(--text-primary, #fff);
  text-decoration: none;
  border-radius: 8px;
  border: 1px solid var(--border-color, #333);
  font-weight: 500;
  transition: all 0.2s ease;
}

.back-button:hover {
  background: var(--primary-color, #42b883);
  border-color: var(--primary-color, #42b883);
  transform: translateY(-1px);
}

.back-button i {
  font-size: 14px;
}

.header-info {
  flex: 1;
}

.header-info h1 {
  margin: 0;
  font-size: 2rem;
  font-weight: 600;
  color: var(--text-primary, #fff);
}

.header-subtitle {
  margin: 4px 0 0 0;
  color: var(--text-secondary, #aaa);
  font-size: 0.9rem;
}

.streamer-content {
  margin-top: 0;
}

@media (max-width: 768px) {
  .streamer-detail-view {
    padding: 16px;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .header-info h1 {
    font-size: 1.5rem;
  }
  
  .back-button {
    padding: 8px 12px;
    font-size: 0.9rem;
  }
}
</style>
