<template>
  <div class="cleanup-policy-editor">
    <div class="policy-card">
      <h4 class="card-title">{{ title }}</h4>
      
      <form @submit.prevent="savePolicy">
        <!-- Use Global Settings Toggle (only for streamers) -->
        <div v-if="!isGlobal" class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="useGlobalPolicy" @change="onGlobalPolicyToggle" />
            Use Global Cleanup Policy
          </label>
          <div class="help-text">
            When enabled, this streamer will use the global cleanup policy settings. 
            Disable to set custom cleanup policy for this streamer.
          </div>
        </div>

        <!-- Policy Configuration (disabled if using global) -->
        <div :class="{ 'disabled-section': !isGlobal && useGlobalPolicy }">
          <!-- Policy Type Selection -->
          <div class="form-group">
            <label>Cleanup Policy:</label>
            <div class="form-row">
              <select v-model="policy.type" class="form-control" :disabled="!isGlobal && useGlobalPolicy">
                <option v-for="type in policyTypes" :key="type.value" :value="type.value">
                  {{ type.label }}
                </option>
              </select>
              <div class="help-text">{{ policyHint }}</div>
            </div>
          </div>

          <!-- Threshold Setting -->
          <div v-if="policy.type !== 'custom'" class="form-group">
            <div class="form-row">
              <label>{{ thresholdLabel }}:</label>
              <input 
                type="number" 
                v-model.number="policy.threshold"
                min="1" 
                class="form-control" 
                :disabled="!isGlobal && useGlobalPolicy"
                required 
              />
              <div class="help-text">{{ thresholdHint }}</div>
            </div>
          </div>

          <!-- Preservation Options -->
          <div class="form-group">
            <label>Preservation Options:</label>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="policy.preserve_favorites" :disabled="!isGlobal && useGlobalPolicy" />
                Preserve favorites
              </label>
            </div>
          </div>

          <!-- Preserve Specific Categories -->
          <div v-if="showPreserveCategories" class="form-group">
            <label>Preserve Categories:</label>
            <select v-model="policy.preserve_categories" class="form-control" multiple :disabled="!isGlobal && useGlobalPolicy">
              <option v-for="category in availableCategories" :key="category.id" :value="category.name">
                {{ category.name }}
              </option>
            </select>
            <div class="help-text">Hold Ctrl/Cmd to select multiple categories</div>
          </div>
        </div>

        <!-- Form Actions -->
        <div class="form-actions">
          <button 
            type="submit" 
            class="btn btn-primary" 
            :disabled="isSaving"
          >
            {{ isSaving ? 'Saving...' : 'Save Cleanup Policy' }}
          </button>
        </div>
      </form>
    </div>

    <!-- Storage Statistics -->
    <div v-if="showStorageStats" class="policy-card">
      <h4 class="card-title">Storage Statistics</h4>
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-label">Total Size</div>
          <div class="stat-value">{{ formatFileSize(storageStats.totalSize) }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">Recording Count</div>
          <div class="stat-value">{{ storageStats.recordingCount }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">Oldest Recording</div>
          <div class="stat-value">{{ formatDate(storageStats.oldestRecording) }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">Newest Recording</div>
          <div class="stat-value">{{ formatDate(storageStats.newestRecording) }}</div>
        </div>
      </div>

      <div class="form-actions">
        <button 
          class="btn btn-danger" 
          @click="runCleanupNow" 
          :disabled="isRunningCleanup"
        >
          {{ isRunningCleanup ? 'Cleaning...' : 'Run Cleanup Now' }}
        </button>
        <button 
          class="btn btn-warning" 
          @click="runCustomCleanupTest" 
          :disabled="isRunningCleanup"
        >
          Test Current Settings
        </button>
      </div>
    </div>

    <!-- Notification Messages -->
    <div v-if="showSnackbar" :class="['message', snackbarColor]">
      {{ snackbarText }}
      <button @click="showSnackbar = false" class="close-btn">&times;</button>
    </div>

    <!-- Cleanup Results Dialog -->
    <div v-if="showCleanupResults" class="modal-overlay" @click="closeCleanupResults">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Cleanup Results</h3>
          <button @click="closeCleanupResults" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <p>{{ cleanupResults.message }}</p>
          <p><strong>Recordings Deleted:</strong> {{ cleanupResults.deleted_count }}</p>
          
          <div v-if="cleanupResults.deleted_paths && cleanupResults.deleted_paths.length > 0">
            <h4>Deleted Files:</h4>
            <ul class="deleted-files-list">
              <li v-for="(path, index) in cleanupResults.deleted_paths" :key="index">
                {{ path }}
              </li>
            </ul>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeCleanupResults" class="btn btn-primary">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import type { CleanupPolicy } from '@/types/recording';
import { CleanupPolicyType } from '@/types/recording';

interface CleanupResults {
  message: string;
  deleted_count: number;
  deleted_paths: string[];
}

interface StorageStats {
  totalSize: number;
  recordingCount: number;
  oldestRecording: string;
  newestRecording: string;
}

interface Category {
  id: number;
  name: string;
}

const props = defineProps<{
  streamerId?: number;
  title: string;
  isGlobal: boolean;
}>();

const emit = defineEmits<{
  saved: [policy: CleanupPolicy];
  updated: [policy: CleanupPolicy];
}>();

const recordingSettings = useRecordingSettings();

// State
const isSaving = ref(false);
const isRunningCleanup = ref(false);
const showSnackbar = ref(false);
const snackbarText = ref('');
const snackbarColor = ref('success');
const showCleanupResults = ref(false);
const useGlobalPolicy = ref(true); // Use global cleanup policy by default
const cleanupResults = ref<CleanupResults>({
  message: '',
  deleted_count: 0,
  deleted_paths: []
});

// Storage stats
const showStorageStats = ref(false);
const storageStats = ref<StorageStats>({
  totalSize: 0,
  recordingCount: 0,
  oldestRecording: '',
  newestRecording: ''
});

// Base policy - simplified without complex timeframe logic
const policy = ref<CleanupPolicy>({
  type: CleanupPolicyType.COUNT,
  threshold: 10,
  preserve_favorites: true,
  preserve_categories: []
});

// Options
const policyTypes = [
  { label: 'Keep X newest recordings', value: CleanupPolicyType.COUNT },
  { label: 'Limit total size (GB)', value: CleanupPolicyType.SIZE },
  { label: 'Delete older than X days', value: CleanupPolicyType.AGE }
];

const availableCategories = ref<Category[]>([]);

// Computed properties
const policyHint = computed(() => {
  switch (policy.value.type) {
    case CleanupPolicyType.COUNT:
      return `Keep only the ${policy.value.threshold} most recent recordings per streamer`;
    case CleanupPolicyType.SIZE:
      return `Delete old recordings when total size exceeds ${policy.value.threshold} GB per streamer`;
    case CleanupPolicyType.AGE:
      return `Delete recordings older than ${policy.value.threshold} days`;
    default:
      return '';
  }
});

const thresholdLabel = computed(() => {
  switch (policy.value.type) {
    case CleanupPolicyType.COUNT:
      return 'Number of recordings to keep';
    case CleanupPolicyType.SIZE:
      return 'Maximum storage size (GB)';
    case CleanupPolicyType.AGE:
      return 'Maximum age (days)';
    default:
      return 'Threshold';
  }
});

const thresholdHint = computed(() => {
  switch (policy.value.type) {
    case CleanupPolicyType.COUNT:
      return 'Keeps the most recent recordings, deletes older ones';
    case CleanupPolicyType.SIZE:
      return 'Deletes oldest recordings when total size exceeds this limit';
    case CleanupPolicyType.AGE:
      return 'Deletes recordings older than this number of days';
    default:
      return '';
  }
});

const showPreserveCategories = computed(() => {
  return availableCategories.value.length > 0;
});

// Methods
async function loadPolicy() {
  try {
    if (props.isGlobal) {
      // Make sure settings are loaded first
      if (!recordingSettings.settings.value) {
        await recordingSettings.fetchSettings();
      }
      
      // Load global cleanup policy from settings
      if (recordingSettings.settings.value?.cleanup_policy) {
        const loadedPolicy = recordingSettings.settings.value.cleanup_policy;
        policy.value = ensureCompletePolicy(loadedPolicy);
      }
    } else if (props.streamerId) {
      // Load storage stats for streamer
      showStorageStats.value = true;
      await loadStorageStats();
      
      // Load streamer-specific policy if available
      await recordingSettings.fetchStreamerSettings();
      const streamerSettings = recordingSettings.streamerSettings.value.find(
        (s: any) => s.streamer_id === props.streamerId
      );
      if (streamerSettings) {
        // Set the global policy toggle based on streamer settings
        useGlobalPolicy.value = streamerSettings.use_global_cleanup_policy !== false;
        
        // Load policy only if not using global settings
        if (!useGlobalPolicy.value && streamerSettings.cleanup_policy) {
          policy.value = ensureCompletePolicy(streamerSettings.cleanup_policy);
        } else {
          // Load global policy as preview when using global settings
          await loadGlobalPolicyAsPreview();
        }
      } else {
        // No streamer settings yet, default to global
        useGlobalPolicy.value = true;
        await loadGlobalPolicyAsPreview();
      }
    }
    
    // Load available categories
    await loadCategories();
  } catch (error) {
    showError('Error loading cleanup policy');
    console.error('Error loading cleanup policy:', error);
  }
}

async function loadCategories() {
  try {
    const categories = await recordingSettings.getAvailableCategories();
    availableCategories.value = categories;
  } catch (error) {
    console.error('Error loading categories:', error);
  }
}

async function loadStorageStats() {
  if (!props.streamerId) return;
  
  try {
    const stats = await recordingSettings.getStreamerStorageUsage(props.streamerId);
    storageStats.value = stats;
  } catch (error) {
    console.error('Error loading storage stats:', error);
  }
}

async function loadGlobalPolicyAsPreview() {
  try {
    if (!recordingSettings.settings.value) {
      await recordingSettings.fetchSettings();
    }
    
    if (recordingSettings.settings.value?.cleanup_policy) {
      const globalPolicy = recordingSettings.settings.value.cleanup_policy;
      policy.value = ensureCompletePolicy(globalPolicy);
    }
  } catch (error) {
    console.error('Error loading global policy preview:', error);
  }
}

function onGlobalPolicyToggle() {
  if (useGlobalPolicy.value) {
    // When switching to global, load global policy as preview
    loadGlobalPolicyAsPreview();
  } else {
    // When switching to custom, reset to default policy
    policy.value = {
      type: CleanupPolicyType.COUNT,
      threshold: 10,
      preserve_favorites: true,
      preserve_categories: []
    };
  }
}

async function savePolicy() {
  try {
    isSaving.value = true;
    
    // Ensure all required properties are present
    const completePolicy = ensureCompletePolicy(policy.value);
    
    if (props.isGlobal) {
      // Save global cleanup policy
      await recordingSettings.updateCleanupPolicy(completePolicy);
    } else if (props.streamerId) {
      // Save streamer-specific cleanup policy with global flag
      await recordingSettings.updateStreamerCleanupPolicy(
        props.streamerId, 
        completePolicy, 
        useGlobalPolicy.value
      );
    }
    
    showSuccess('Cleanup policy saved successfully');
    emit('saved', completePolicy);
    
  } catch (error) {
    showError('Error saving cleanup policy');
    console.error('Error saving cleanup policy:', error);
  } finally {
    isSaving.value = false;
  }
}

async function runCleanupNow() {
  if (!props.streamerId) return;
  
  try {
    isRunningCleanup.value = true;
    
    const response = await recordingSettings.cleanupOldRecordings(props.streamerId);
    
    // Show results dialog with the response from the server
    cleanupResults.value = {
      message: response.message || 'Cleanup completed successfully',
      deleted_count: response.deleted_count || 0,
      deleted_paths: response.deleted_paths || []
    };
    showCleanupResults.value = true;
    
    // Refresh storage stats
    await loadStorageStats();
    
  } catch (error) {
    showError('Error running cleanup');
    console.error('Error running cleanup:', error);
  } finally {
    isRunningCleanup.value = false;
  }
}

async function runCustomCleanupTest() {
  if (!props.streamerId) return;
  
  try {
    isRunningCleanup.value = true;
    
    // Ensure all required properties are present
    const completePolicy = ensureCompletePolicy(policy.value);
    
    const result = await recordingSettings.runCustomCleanup(props.streamerId, completePolicy);
    
    // Show results dialog
    cleanupResults.value = {
      message: result.message || `Test cleanup would delete ${result.deleted_count} recordings`,
      deleted_count: result.deleted_count || 0,
      deleted_paths: result.deleted_paths || []
    };
    showCleanupResults.value = true;
    
    // Refresh storage stats
    await loadStorageStats();
    
  } catch (error) {
    showError('Error running custom cleanup test');
    console.error('Error running custom cleanup:', error);
  } finally {
    isRunningCleanup.value = false;
  }
}

function closeCleanupResults() {
  showCleanupResults.value = false;
  cleanupResults.value = {
    message: '',
    deleted_count: 0,
    deleted_paths: []
  };
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(isoDate: string): string {
  if (!isoDate) return 'N/A';
  
  try {
    return new Date(isoDate).toLocaleString();
  } catch (error) {
    return 'Invalid date';
  }
}

function showSuccess(message: string) {
  snackbarText.value = message;
  snackbarColor.value = 'success';
  showSnackbar.value = true;
  setTimeout(() => {
    showSnackbar.value = false;
  }, 5000);
}

function showError(message: string) {
  snackbarText.value = message;
  snackbarColor.value = 'error';
  showSnackbar.value = true;
  setTimeout(() => {
    showSnackbar.value = false;
  }, 8000);
}

// Helper function to ensure policy has all required properties
function ensureCompletePolicy(policyObj: CleanupPolicy): CleanupPolicy {
  return {
    type: policyObj.type || CleanupPolicyType.COUNT,
    threshold: policyObj.threshold || 10,
    preserve_favorites: policyObj.preserve_favorites !== undefined ? policyObj.preserve_favorites : true,
    preserve_categories: policyObj.preserve_categories || []
  };
}

// Load initial data
onMounted(() => {
  loadPolicy();
});
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.cleanup-policy-editor {
  max-width: 100%;
}

.policy-card {
  padding: 20px;
  border-radius: var(--border-radius, 8px);
  margin-bottom: 20px;
}

.card-title {
  margin: 0 0 20px 0;
  color: var(--text-primary, #f1f1f3);
  font-size: 1.2rem;
  font-weight: 600;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

@include m.respond-below('md') {  // < 768px
  .form-row {
    grid-template-columns: 1fr;
  }
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--text-primary, #f1f1f3);
}

.checkbox-label {
  display: flex;
  align-items: flex-start;
  font-weight: normal;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  margin-right: 8px;
  margin-top: 2px;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-control {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color, #303034);
  background-color: var(--background-dark, #18181b);
  color: var(--text-primary, #f1f1f3);
  border-radius: var(--border-radius, 6px);
  box-sizing: border-box;
  font-size: 14px;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color, #42b883);
  box-shadow: 0 0 0 2px rgba(66, 184, 131, 0.2);
}

select.form-control {
  background-image: linear-gradient(45deg, transparent 50%, var(--text-primary, #f1f1f3) 50%),
                    linear-gradient(135deg, var(--text-primary, #f1f1f3) 50%, transparent 50%);
  background-position: calc(100% - 15px) calc(1em + 2px),
                       calc(100% - 10px) calc(1em + 2px);
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 30px;
  appearance: none;
}

select.form-control option {
  background-color: var(--background-darker, #1f1f23);
  color: var(--text-primary, #f1f1f3);
  padding: 8px;
}

.help-text {
  font-size: 0.85rem;
  color: var(--text-secondary, #adadb8);
  margin-top: 4px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.stat-item {
  background-color: var(--background-dark, #18181b);
  padding: 15px;
  border-radius: var(--border-radius, 6px);
  border: 1px solid var(--border-color, #303034);
}

.stat-label {
  font-size: 0.9rem;
  color: var(--text-secondary, #adadb8);
  margin-bottom: 5px;
}

.stat-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary, #f1f1f3);
}

.form-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn {
  padding: 10px 20px;
  border-radius: var(--border-radius, 6px);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  font-size: 14px;
}

.btn-primary {
  background-color: var(--primary-color, #42b883);
  color: white;
}

.btn-secondary {
  background-color: var(--secondary-color, #6c757d);
  color: white;
}

.btn-warning {
  background-color: var(--warning-color, #ffc107);
  color: #212529;
}

.btn-danger {
  background-color: var(--danger-color, #dc3545);
  color: white;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.message {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  border-radius: var(--border-radius, 6px);
  margin-bottom: 20px;
  font-weight: 500;
}

.message.success {
  background-color: rgba(40, 167, 69, 0.2);
  color: var(--success-color, #28a745);
  border: 1px solid rgba(40, 167, 69, 0.3);
}

.message.error {
  background-color: rgba(220, 53, 69, 0.2);
  color: var(--danger-color, #dc3545);
  border: 1px solid rgba(220, 53, 69, 0.3);
}

.close-btn {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--text-secondary, #adadb8);
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background-color 0.2s ease;
}

.close-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #f1f1f3);
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background-color: var(--background-darker, #1f1f23);
  border-radius: var(--border-radius, 8px);
  border: 1px solid var(--border-color, #303034);
  max-width: 90vw;
  max-height: 90vh;
  width: 600px;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color, #303034);
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary, #f1f1f3);
}

.modal-header .close-btn {
  font-size: 24px;
  width: 30px;
  height: 30px;
}

.modal-body {
  padding: 20px;
  color: var(--text-primary, #f1f1f3);
}

.modal-footer {
  padding: 20px;
  border-top: 1px solid var(--border-color, #303034);
  display: flex;
  justify-content: flex-end;
}

.deleted-files-list {
  max-height: 300px;
  overflow-y: auto;
  background-color: var(--background-dark, #18181b);
  border: 1px solid var(--border-color, #303034);
  border-radius: var(--border-radius, 6px);
  padding: 15px;
  margin: 10px 0;
  list-style: none;
}

.deleted-files-list li {
  padding: 5px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  font-family: monospace;
  font-size: 0.9rem;
  word-break: break-all;
}

.deleted-files-list li:last-child {
  border-bottom: none;
}

/* Disabled section styles */
.disabled-section {
  opacity: 0.5;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.disabled-section .form-control:disabled,
.disabled-section input:disabled,
.disabled-section select:disabled {
  background-color: var(--background-dark, #18181b);
  color: var(--text-secondary, #adadb8);
  border-color: var(--border-color, #303034);
  cursor: not-allowed;
}
</style>
