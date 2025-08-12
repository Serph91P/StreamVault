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
        
        <!-- Actions -->
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
          <button 
            @click="confirmDeleteAll"
            class="btn btn-danger"
            :disabled="deletingAll"
            title="Delete all streams except those currently recording"
          >
            <span v-if="deletingAll">
              <i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Deleting...
            </span>
            <span v-else>
              <i class="fas fa-trash-alt" aria-hidden="true"></i> Delete All (safe)
            </span>
          </button>
        </div>
      </div>
      
      <div class="streamer-content">
        <StreamList :hide-header="true" />
      </div>
      
      <!-- Confirm Delete All Modal -->
      <div v-if="showConfirm" class="modal-overlay" @click.self="showConfirm = false">
        <div class="modal">
          <div class="modal-header">
            <h3>Delete All Streams</h3>
            <button class="close-btn" @click="showConfirm = false">×</button>
          </div>
          <div class="modal-body">
            <p>Delete all streams for this streamer?</p>
            <p class="warning">Active recordings will be skipped to avoid data loss.</p>
          </div>
          <div class="modal-actions">
            <button class="btn btn-secondary" @click="showConfirm = false">Cancel</button>
            <button class="btn btn-danger" :disabled="deletingAll" @click="deleteAll">{{ deletingAll ? '⏳ Deleting...' : '🗑️ Delete All' }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { computed, ref } from 'vue'
import StreamList from '@/components/StreamList.vue'
import { useForceRecording } from '@/composables/useForceRecording'
import { streamersApi } from '@/services/api'

const route = useRoute()
const router = useRouter()
const streamerName = computed(() => route.query.name as string)
const streamerId = computed(() => route.params.id as string)

// Use Force Recording Composable
const { forceRecordingStreamerId, forceStartRecording } = useForceRecording()

// Delete all (except currently recording) flow
const showConfirm = ref(false)
const deletingAll = ref(false)
const confirmDeleteAll = () => { showConfirm.value = true }
const deleteAll = async () => {
  if (!streamerId.value) return
  try {
    deletingAll.value = true
    await streamersApi.deleteAllStreams(Number(streamerId.value), { excludeActive: true })
    showConfirm.value = false
    router.push('/streamers')
  } catch (e) {
    console.error('Failed to delete all streams:', e)
  } finally {
    deletingAll.value = false
  }
}
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

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header { padding: 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); }
.modal-actions { padding: 16px; display: flex; justify-content: center; align-items: center; gap: 12px; border-top: 1px solid var(--border-color); position: sticky; bottom: 0; background: var(--background-card); }
.modal-body { padding: 16px; overflow: auto; }
.warning { color: var(--danger-color); }
.close-btn { background: none; border: none; color: var(--text-secondary); font-size: 1.5rem; cursor: pointer; }

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
