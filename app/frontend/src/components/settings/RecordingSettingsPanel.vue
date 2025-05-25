<template>
  <div>
    <h3>Recording Settings</h3>
    
    <div v-if="isLoading" class="loading-message">
      Loading recording settings...
    </div>
    
    <div v-else-if="error" class="error-message">
      Error loading settings: {{ error }}
    </div>
    
    <!-- Global Settings -->
    <div v-else class="settings-form">
      <div class="form-group">
        <label>
          <input type="checkbox" v-model="data.enabled" />
          Enable Stream Recording
        </label>
      </div>

      <div class="form-group">
        <label>Output Directory:</label>
        <input v-model="data.output_directory" placeholder="/recordings" class="form-control" />
        <div class="help-text">
          Directory inside the Docker container where recordings are saved.
          You can mount this to your host system in docker-compose.yml.
        </div>
      </div>

      <div class="form-group">
        <label>Filename Preset:</label>
        <select v-model="data.filename_preset" class="form-control" @change="updateFilenameTemplate">
          <option v-for="preset in FILENAME_PRESETS" :key="preset.value" :value="preset.value">
            {{ preset.label }}
          </option>
        </select>
        <div class="help-text">
          Select a preset for media server compatibility or use a custom template below.
        </div>
      </div>

      <div class="form-group">
        <label>Filename Template:</label>
        <input v-model="data.filename_template"
          placeholder="{streamer}/{streamer}_{year}{month}-{day}_{hour}-{minute}_{title}_{game}"
          class="form-control" />
        <div class="filename-preview" v-if="data.filename_template">
          <strong>Preview:</strong> {{ previewFilename }}
        </div>
        <div class="variables-list">
          <strong>Available Variables:</strong>
          <div class="variables-grid">
            <div v-for="variable in FILENAME_VARIABLES" :key="variable.key" class="variable-item">
              <code>{{ '{' + variable.key + '}' }}</code> - {{ variable.description }}
            </div>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label>Default Quality:</label>
        <select v-model="data.default_quality" class="form-control">
          <option v-for="option in QUALITY_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <div class="help-text">
          Default quality for all streamers. This can be overridden on a per-streamer basis.
        </div>
      </div>

      <div class="form-group">
        <label>
          <input type="checkbox" v-model="data.use_chapters" />
          Create Chapters From Stream Events
        </label>
        <div class="help-text">
          Create chapters in the recording based on stream title and game changes.
        </div>
      </div>

      <div class="form-group">
        <label>
          <input type="checkbox" v-model="data.use_category_as_chapter_title" />
          Use Category as Chapter Title
        </label>
        <div class="help-text">
          When enabled, chapter titles will use the game/category name instead of the stream title.
        </div>
      </div>
      
      <div class="form-group">
        <label>Maximum Streams Per Streamer:</label>
        <input v-model.number="data.max_streams_per_streamer" type="number" min="0" class="form-control" />
        <div class="help-text">
          Maximum number of recordings to keep per streamer (0 = unlimited). When this limit is reached,
          the oldest recordings will be automatically deleted.
        </div>
      </div>
      
      <!-- Advanced Cleanup Policy -->
      <div class="form-group">
        <h4 class="section-title">Advanced Cleanup Policy</h4>
        <p class="section-description">
          Configure more advanced rules for automatic cleanup of old recordings.
        </p>
        
        <CleanupPolicyEditor
          :is-global="true"
          title="Global Cleanup Policy"
          @saved="handleCleanupPolicySaved"
        />
      </div>

      <div class="form-actions">
        <button @click="saveSettings" class="btn btn-primary" :disabled="isSaving">
          {{ isSaving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
    </div>

    <!-- Active Recordings -->
    <div v-if="activeRecordings.length > 0" class="active-recordings">
      <h3>Active Recordings</h3>
      <div class="recordings-grid">
        <div v-for="recording in activeRecordings" :key="recording.streamer_id" class="recording-card">
          <div class="recording-header">
            <span class="streamer-name">{{ recording.streamer_name }}</span>
            <span class="recording-indicator">RECORDING</span>
          </div>
          <div class="recording-details">
            <div><strong>Started:</strong> {{ formatDate(recording.started_at) }}</div>
            <div><strong>Duration:</strong> {{ formatDuration(recording.duration) }}</div>
            <div><strong>Quality:</strong> {{ recording.quality }}</div>
            <div class="output-path"><strong>Output:</strong> {{ recording.output_path }}</div>
          </div>
          <button @click="stopRecording(recording.streamer_id)" class="btn btn-danger" :disabled="isLoading">
            Stop Recording
          </button>
        </div>
      </div>
    </div>
    <!-- Streamer Settings -->
    <div class="streamer-settings">
      <h3>Streamer Recording Settings</h3>
      
      <div v-if="!streamerSettings || streamerSettings.length === 0" class="no-streamers-message">
        <p>No streamers found. Add streamers in the Streamers section to configure recording settings.</p>
      </div>
        <template v-else>
        <div class="table-controls">
          <button @click="toggleAllStreamers(true)" class="btn btn-secondary">Enable All</button>
          <button @click="toggleAllStreamers(false)" class="btn btn-secondary">Disable All</button>
        </div>

        <div class="streamer-table">
          <table>
            <thead>
              <tr>
                <th>Streamer</th>
                <th>
                  Record
                  <div class="th-tooltip">Enable/disable recording for this streamer</div>
                </th>
                <th>
                  Quality
                  <div class="th-tooltip">Select recording quality (defaults to global setting if empty)</div>
                </th>
                <th>
                  Custom Filename
                  <div class="th-tooltip">Optional custom filename template for this streamer</div>
                </th>
                <th>
                  Max Streams
                  <div class="th-tooltip">Maximum number of recordings to keep (0 = use global setting)</div>
                </th>
                <th>
                  Actions
                  <div class="th-tooltip">Test, stop, or clean up recordings</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="streamer in streamerSettings" :key="streamer.streamer_id">
                <td class="streamer-info">
                  <div class="streamer-avatar" v-if="streamer.profile_image_url">
                    <img :src="streamer.profile_image_url" :alt="streamer.username || ''" />
                  </div>
                  <span class="streamer-name">{{ streamer.username || 'Unknown Streamer' }}</span>
                </td>
                <td>
                  <input type="checkbox" v-model="streamer.enabled"
                    @change="updateStreamerSetting(streamer.streamer_id, { enabled: streamer.enabled })" />
                </td>
                <td>
                  <select v-model="streamer.quality"
                    @change="updateStreamerSetting(streamer.streamer_id, { quality: streamer.quality })"
                    class="form-control form-control-sm">
                    <option value="">Use global default</option>
                    <option v-for="option in QUALITY_OPTIONS" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </td>
                <td>
                  <input type="text" v-model="streamer.custom_filename"
                    @change="updateStreamerSetting(streamer.streamer_id, { custom_filename: streamer.custom_filename })"
                    placeholder="Use global template" class="form-control form-control-sm" />
                </td>
                <td>
                  <input type="number" v-model.number="streamer.max_streams" min="0"
                    @change="updateStreamerSetting(streamer.streamer_id, { max_streams: streamer.max_streams })"
                    placeholder="0" class="form-control form-control-sm" />
                </td>
                <td>
                  <div class="streamer-actions">
                    <button 
                      v-if="isActiveRecording(streamer.streamer_id)" 
                      @click="stopRecording(streamer.streamer_id)" 
                      class="btn btn-danger btn-sm" 
                      :disabled="isLoading">
                      Stop
                    </button>
                    <button 
                      @click="cleanupStreamerRecordings(streamer.streamer_id)" 
                      class="btn btn-warning btn-sm" 
                      :disabled="isLoading || (!streamer.max_streams && !data.max_streams_per_streamer)" 
                      :title="(!streamer.max_streams && !data.max_streams_per_streamer) ? 'Set max recordings first' : 'Delete old recordings'">
                      Clean
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { QUALITY_OPTIONS, FILENAME_VARIABLES, FILENAME_PRESETS } from '@/types/recording';
import type { RecordingSettings, StreamerRecordingSettings } from '@/types/recording';
import CleanupPolicyEditor from '@/components/CleanupPolicyEditor.vue';

const props = defineProps<{
  settings: RecordingSettings | null;
  streamerSettings: StreamerRecordingSettings[];
  activeRecordings: any[];
}>();

const emits = defineEmits<{
  update: [settings: RecordingSettings];
  updateStreamer: [streamerId: number, settings: Partial<StreamerRecordingSettings>];
  stopRecording: [streamerId: number];
  cleanupRecordings: [streamerId: number];
}>();

const { isLoading, error } = useRecordingSettings();

// Create a copy of the settings for editing
const data = ref<RecordingSettings>({
  enabled: props.settings?.enabled ?? false,
  output_directory: props.settings?.output_directory ?? '/recordings',
  filename_template: props.settings?.filename_template ?? '{streamer}/{streamer}_{year}{month}-{day}_{hour}-{minute}_{title}_{game}',
  filename_preset: props.settings?.filename_preset,
  default_quality: props.settings?.default_quality ?? 'best',
  use_chapters: props.settings?.use_chapters ?? true,
  use_category_as_chapter_title: props.settings?.use_category_as_chapter_title ?? false,
  max_streams_per_streamer: props.settings?.max_streams_per_streamer ?? 0
});

const updateFilenameTemplate = () => {
  const preset = FILENAME_PRESETS.find(p => p.value === data.value.filename_preset);
  if (preset) {
    data.value.filename_template = preset.description;
  }
};

// Update local data when props change
watch(() => props.settings, (newSettings) => {
  if (newSettings) {
    data.value = { ...newSettings };
  }
}, { deep: true });

const isSaving = ref(false);

// Preview filename with example data
const previewFilename = computed(() => {
  if (!data.value.filename_template) return '';

  const now = new Date();
  const year = now.getFullYear().toString();
  const month = (now.getMonth() + 1).toString().padStart(2, '0');
  const day = now.getDate().toString().padStart(2, '0');
  const hour = now.getHours().toString().padStart(2, '0');
  const minute = now.getMinutes().toString().padStart(2, '0');
  const second = now.getSeconds().toString().padStart(2, '0');

  let filename = data.value.filename_template;

  // Replace variables
  filename = filename
    .replace(/{streamer}/g, 'example_streamer')
    .replace(/{title}/g, 'Example Stream Title')
    .replace(/{game}/g, 'Example Game')
    .replace(/{twitch_id}/g, '123456789')
    .replace(/{year}/g, year)
    .replace(/{month}/g, month)
    .replace(/{day}/g, day)
    .replace(/{hour}/g, hour)
    .replace(/{minute}/g, minute)
    .replace(/{second}/g, second)
    .replace(/{timestamp}/g, `${year}${month}${day}_${hour}${minute}${second}`)
    .replace(/{datetime}/g, `${year}-${month}-${day}_${hour}-${minute}-${second}`)
    .replace(/{id}/g, 'stream_12345')
    .replace(/{season}/g, `S${year}-${month}`)
    .replace(/{episode}/g, '01');

  // Add .mp4 if not present
  if (!filename.toLowerCase().endsWith('.mp4')) {
    filename += '.mp4';
  }

  return filename;
});

const saveSettings = async () => {
  try {
    isSaving.value = true;      emits('update', {
      enabled: data.value.enabled,
      output_directory: data.value.output_directory,
      filename_template: data.value.filename_template,
      filename_preset: data.value.filename_preset,
      default_quality: data.value.default_quality,
      use_chapters: data.value.use_chapters,
      use_category_as_chapter_title: data.value.use_category_as_chapter_title,
      max_streams_per_streamer: data.value.max_streams_per_streamer
    });
  } catch (error) {
    console.error('Failed to save settings:', error);
    alert('Failed to save settings. Please try again.');
  } finally {
    isSaving.value = false;
  }
};

const updateStreamerSetting = (streamerId: number, settings: Partial<StreamerRecordingSettings>) => {
  emits('updateStreamer', streamerId, settings);
};

const toggleAllStreamers = async (enabled: boolean) => {
  if (!props.streamerSettings) return;

  for (const streamer of props.streamerSettings) {
    if (!streamer?.streamer_id) continue;
    await updateStreamerSetting(streamer.streamer_id, { enabled });
  }
};

const stopRecording = (streamerId: number) => {
  emits('stopRecording', streamerId);
};

const cleanupStreamerRecordings = (streamerId: number) => {
  if (confirm('Are you sure you want to clean up old recordings for this streamer? This action cannot be undone.')) {
    emits('cleanupRecordings', streamerId);
  }
};

const isActiveRecording = (streamerId: number): boolean => {
  return props.activeRecordings.some(rec => rec.streamer_id === streamerId);
};

const formatDate = (date: string) => {
  return new Date(date).toLocaleString();
};

const formatDuration = (seconds: number) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
};

const toggleStreamerRecording = (streamerId: number, enabled: boolean) => {
  updateStreamerSetting(streamerId, { enabled });
};

const handleCleanupPolicySaved = (policy: any) => {
  if (props.settings) {
    const updatedSettings = { 
      ...props.settings, 
      cleanup_policy: policy 
    };
    emits('update', updatedSettings);
  }
};
</script>

<style scoped>
/* Mobile-First-Ansatz - Basis-Styles für mobile Geräte */

.settings-form,
.active-recordings,
.streamer-settings {
  margin-bottom: 30px;
  background-color: var(--background-darker, #1f1f23);
  padding: 20px;
  border-radius: var(--border-radius, 8px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  border: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: var(--spacing-lg, 20px);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-sm, 8px);
  font-weight: 500;
}

/* Ensure form controls are properly styled */
.form-control {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color);
  background-color: var(--background-dark, #18181b);
  color: var(--text-primary, #f1f1f3);
  border-radius: var(--border-radius);
  box-sizing: border-box;
}

/* Style for select elements to make them more visible */
select.form-control {
  appearance: auto; /* Re-enable native appearance for better visibility */
  background-color: var(--background-dark, #18181b);
  color: var(--text-primary, #f1f1f3);
  background-image: linear-gradient(45deg, transparent 50%, var(--primary-color) 50%),
                    linear-gradient(135deg, var(--primary-color) 50%, transparent 50%);
  background-position: calc(100% - 20px) calc(1em + 2px),
                       calc(100% - 15px) calc(1em + 2px);
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 30px; /* Make room for the arrow */
}

/* Show dropdown options with better contrast */
select.form-control option {
  background-color: var(--background-darker, #18181b);
  color: var(--text-primary, #f1f1f3);
  padding: 8px;
}

.help-text {
  font-size: 0.85rem;
  color: var(--text-secondary, #adadb8);
  margin-top: var(--spacing-xs, 0.25rem);
}

.checkbox-group label {
  display: flex;
  align-items: flex-start;
  font-weight: normal;
  text-align: left;
}

.checkbox-group input[type="checkbox"] {
  margin-right: var(--spacing-sm, 8px);
  margin-top: 4px;
}

.loading-message, .error-message {
  padding: var(--spacing-md, 1rem);
  margin-bottom: var(--spacing-md, 1rem);
  border-radius: var(--border-radius, 0.25rem);
}

.loading-message {
  background-color: var(--background-darker, #1f1f23);
  color: var(--text-secondary, #adadb8);
}

.error-message {
  background-color: rgba(220, 53, 69, 0.2); 
  color: var(--danger-color, #dc3545);
  border: 1px solid rgba(220, 53, 69, 0.3);
}

/* Verbesserte Mobile-Ansicht für Tabellen */
.streamer-table {
  width: 100%;
  overflow-x: auto;
  background-color: var(--background-darker, #1f1f23);
  border-radius: var(--border-radius, 6px);
  border: 1px solid var(--border-color, #303034);
}

/* Card-basierte Layout für kleine Bildschirme */
@media (max-width: 767px) {
  .streamer-table table {
    border-collapse: separate;
    border-spacing: 0;
  }
  
  .streamer-table thead {
    display: none; /* Header auf Mobilgeräten ausblenden */
  }
  
  .streamer-table tbody tr {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius-sm);
    margin-bottom: 16px;
    padding: 12px;
    background-color: rgba(0, 0, 0, 0.2);
  }
  
  .streamer-table td {
    display: flex;
    padding: 8px 0;
    border: none;
    position: relative;
  }
  
  .streamer-table td:not(:last-child) {
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  
  .streamer-table td::before {
    content: attr(data-label);
    width: 40%;
    font-weight: bold;
    margin-right: 12px;
  }
  
  .streamer-table td:first-child {
    padding-top: 0;
  }
    .streamer-table .form-control-sm {
    width: 100%;
    background-color: var(--background-dark, #18181b);
    color: var(--text-primary, #f1f1f3);
  }
}

/* Verbesserte Tooltips, die nicht den Fluss stören */
.th-tooltip {
  position: relative;
  display: inline-block;
  margin-left: 4px;
  color: var(--text-secondary, #ccc);
  font-size: 0.75rem;
}

/* Aktionsbuttons besser anpassen */
.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 767px) {
  .form-actions {
    flex-direction: column;
  }
  
  .form-actions button {
    width: 100%;
  }
}

/* Remove horizontal stripes */
.streamer-table table tr:nth-child(odd) {
  background-color: transparent;
}

.streamer-table table tr:nth-child(even) {
  background-color: rgba(0, 0, 0, 0.15);
}

.streamer-table {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  background-color: var(--background-darker, #1f1f23);
  border-radius: var(--border-radius, 6px);
  border: 1px solid var(--border-color, #303034);
}

.streamer-table table {
  width: 100%;
  min-width: 600px;
  border-collapse: collapse;
  table-layout: fixed;
}

.streamer-table th, 
.streamer-table td {
  padding: 0.75rem;
  border-bottom: 1px solid var(--border-color, #303034);
  vertical-align: middle;
  text-align: left;
}

.streamer-table th {
  background-color: rgba(0, 0, 0, 0.2);
  font-weight: 500;
  color: var(--text-secondary, #ccc);
}

.th-tooltip {
  font-size: 0.75rem;
  font-weight: normal;
  color: var(--text-secondary, #adadb8);
  margin-top: var(--spacing-xs, 0.25rem);
}

.streamer-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 0.5rem);
  max-width: 100%; /* Ensure content doesn't overflow */
}

.streamer-avatar {
  width: 30px;
  height: 30px;
  margin-right: var(--spacing-sm, 10px);
  overflow: hidden;
  border-radius: 50%;
  flex-shrink: 0;
}

.streamer-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.streamer-name {
  font-size: 1rem;
  font-weight: 500;
  color: var(--text-primary, #efeff1);
  white-space: normal; /* Allow text to wrap */
  word-break: break-word; /* Break long words if needed */
  overflow: visible; /* Remove text truncation */
}

.form-actions {
  display: flex;
  gap: var(--spacing-sm, 10px);
  margin-top: var(--spacing-lg, 20px);
}

.variables-list {
  margin-top: var(--spacing-sm, 0.5rem);
  font-size: 0.9rem;
}

.variables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: var(--spacing-sm, 0.5rem);
  margin-top: var(--spacing-sm, 0.5rem);
}

.variable-item {
  font-size: 0.85rem;
}

.filename-preview {
  margin-top: var(--spacing-sm, 0.5rem);
  padding: var(--spacing-sm, 0.5rem);
  background-color: var(--background-dark, #343a40);
  border-radius: var(--border-radius, 0.25rem);
  font-size: 0.9rem;
  word-break: break-all;
  color: var(--text-primary, #f8f9fa);
  border: 1px solid var(--border-color, #495057);
}

.btn {
  padding: 8px 16px;
  border-radius: var(--border-radius, 6px);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn-primary {
  background-color: var(--primary-color, #42b883);
  color: white;
}

.btn-secondary {
  background-color: var(--background-darker, #3a3a3a);
  color: white;
}

.btn-danger {
  background-color: var(--danger-color, #dc3545);
  color: white;
}

.btn-warning {
  background-color: var(--warning-color, #ffc107);
  color: #212529;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.btn:active:not(:disabled) {
  transform: translateY(1px);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.active-recordings {
  margin-top: var(--spacing-xl, 2rem);
}

.recordings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--spacing-md, 1rem);
  margin-top: var(--spacing-md, 1rem);
}

.recording-card {
  border: 1px solid var(--border-color, #303034);
  border-radius: var(--border-radius, 0.5rem);
  padding: var(--spacing-md, 1rem);
  background-color: var(--background-darker, #1f1f23);
  color: var(--text-primary, #efeff1);
}

.recording-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm, 0.5rem);
}

.recording-indicator {
  background-color: var(--danger-color, #dc3545);
  color: white;
  padding: 0.2rem 0.5rem;
  border-radius: var(--border-radius, 0.25rem);
  font-size: 0.8rem;
  font-weight: bold;
}

.recording-details {
  margin-bottom: var(--spacing-md, 1rem);
  color: var(--text-secondary, #adadb8);
}

.output-path {
  margin-top: var(--spacing-sm, 0.5rem);
  font-size: 0.9rem;
  word-break: break-all;
  color: var(--text-secondary, #adadb8);
}

.streamer-settings {
  margin-top: var(--spacing-xl, 2rem);
}

.table-controls {
  display: flex;
  gap: var(--spacing-sm, 10px);
  margin-bottom: var(--spacing-md, 15px);
}

.no-streamers-message {
  padding: var(--spacing-md, 1rem);
  text-align: center;
  color: var(--text-secondary, #999);
}

.form-control-sm {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border-color);
  background-color: var(--background-dark, #18181b);
  color: var(--text-primary, #f1f1f3);
  border-radius: var(--border-radius);
  box-sizing: border-box;
}

/* Style for small select elements */
select.form-control-sm {
  appearance: auto;
  background-color: var(--background-dark, #18181b);
  color: var(--text-primary, #f1f1f3);
  background-image: linear-gradient(45deg, transparent 50%, var(--primary-color) 50%),
                    linear-gradient(135deg, var(--primary-color) 50%, transparent 50%);
  background-position: calc(100% - 20px) calc(1em + 0px),
                       calc(100% - 15px) calc(1em + 0px);
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 30px;
}

select.form-control-sm option {
  background-color: var(--background-darker, #18181b);
  color: var(--text-primary, #f1f1f3);
  padding: 6px;
}

@media (min-width: 768px) {
  .streamer-table th, 
  .streamer-table td {
    padding: 0.75rem;
    font-size: 1rem;
  }
  
  .streamer-avatar {
    width: 30px;
    height: 30px;
  }
  
  .streamer-name {
    font-size: 1rem;
  }
  
  .btn-action {
    padding: 0.35rem 0.5rem;
  }
}

@media (min-width: 1200px) {
  .streamer-table table {
    table-layout: fixed;
  }
  
  .btn-action {
    font-size: 0.875rem;
  }
}

@media (min-width: 1600px) {
  .button-container {
    flex-direction: row;
  }
}

.streamer-actions {
  display: flex;
  gap: 5px;
}

.streamer-actions .btn {
  flex: 1;
  padding: 4px 8px;
  font-size: 0.75rem;
}
</style>