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

const props = defineProps<{
  settings: RecordingSettings | null;
  streamerSettings: StreamerRecordingSettings[];
  activeRecordings: any[];
}>();

const emits = defineEmits<{
  update: [settings: RecordingSettings];
  updateStreamer: [streamerId: number, settings: Partial<StreamerRecordingSettings>];
  testRecording: [streamerId: number];
  stopRecording: [streamerId: number];
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
  use_category_as_chapter_title: props.settings?.use_category_as_chapter_title ?? false
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
    .replace(/{season}/g, `S${year}-${month}`);

  // Add .mp4 if not present
  if (!filename.toLowerCase().endsWith('.mp4')) {
    filename += '.mp4';
  }

  return filename;
});

const saveSettings = async () => {
  try {
    isSaving.value = true;
    emits('update', {
      enabled: data.value.enabled,
      output_directory: data.value.output_directory,
      filename_template: data.value.filename_template,
      filename_preset: data.value.filename_preset,
      default_quality: data.value.default_quality,
      use_chapters: data.value.use_chapters,
      use_category_as_chapter_title: data.value.use_category_as_chapter_title
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

const testRecording = (streamerId: number) => {
  emits('testRecording', streamerId);
};

const stopRecording = (streamerId: number) => {
  emits('stopRecording', streamerId);
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
</script>

<style scoped>
/* Mobile-First-Ansatz - Basis-Styles für mobile Geräte */

.streamer-table {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.streamer-table table {
  width: 100%;
  min-width: 600px;
  border-collapse: collapse;
  table-layout: fixed;
}

.streamer-table th, 
.streamer-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #303034;
  vertical-align: middle;
  text-align: left;
}

.streamer-table th:nth-child(1),
.streamer-table td:nth-child(1) {
  width: 40%;
  min-width: 200px;
  white-space: normal;
  word-break: break-word;
}

.streamer-table th:nth-child(2),
.streamer-table td:nth-child(2) {
  width: 10%;
  text-align: center;
}

.streamer-table th:nth-child(3),
.streamer-table td:nth-child(3) {
  width: 15%;
}

.streamer-table th:nth-child(4),
.streamer-table td:nth-child(4) {
  width: 35%;
}

/* Verbesserte lesbarkeit für mobile Geräte */
.streamer-table th {
  font-weight: 600;
  background-color: rgba(0, 0, 0, 0.2);
}

/* Optimierte Spaltenbreiten für mobile Ansicht */
.streamer-table th:nth-child(1),
.streamer-table td:nth-child(1) {
  width: 25%; /* Increase from previous value */
  min-width: 150px; /* Ensure minimum width */
  white-space: normal; /* Allow text to wrap */
  word-break: break-word; /* Break long words if needed */
}

.streamer-table th:nth-child(2),
.streamer-table td:nth-child(2) {
  width: 15%;
  text-align: center;
}

.streamer-table th:nth-child(3),
.streamer-table td:nth-child(3) {
  width: 20%;
}

.streamer-table th:nth-child(4),
.streamer-table td:nth-child(4) {
  width: 20%;
}

.streamer-table th:nth-child(5),
.streamer-table td:nth-child(5) {
  width: 15%;
}

/* Mobile-optimierte Button-Container */
.action-buttons {
  width: 100%;
}

.button-container {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  align-items: stretch;
}

/* Touch-freundliche Buttons */
.btn-action {
  padding: 0.5rem;  /* Größere Touch-Fläche */
  font-size: 0.8rem;
  white-space: nowrap;
  width: 100%;
  display: inline-block;
  text-align: center;
  background-color: #2f2f2f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
  touch-action: manipulation; /* Verbessert Touch-Handling */
}

.btn-action:first-child {
  background-color: #2f3f2f;
}

.btn-action:last-child {
  background-color: #3f2f2f;
}

/* Touch-freundliche Formularelemente */
.form-control-sm {
  width: 100%;
  height: 36px; /* Größere Touch-Fläche */
  font-size: 0.875rem;
  padding: 0.5rem;
  background: #18181b;
  border: 1px solid #303034;
  color: #efeff1;
  border-radius: 4px;
}

/* Bessere Darstellung der Streamer-Info */
.streamer-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 100%; /* Ensure content doesn't overflow */
}

.streamer-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  overflow: hidden;
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
  color: #efeff1;
  white-space: normal; /* Allow text to wrap */
  word-break: break-word; /* Break long words if needed */
  overflow: visible; /* Remove text truncation */
}

/* Für Tablets und größere Bildschirme */
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
  
  /* Angepasste Spaltenbreiten für größere Bildschirme */
  .streamer-table th:nth-child(1),
  .streamer-table td:nth-child(1) {
    width: 25%;
  }
  
  .streamer-table th:nth-child(4),
  .streamer-table td:nth-child(4) {
    width: 30%;
  }
}

/* Für Desktop und große Bildschirme */
@media (min-width: 1200px) {
  .streamer-table table {
    table-layout: fixed; /* Für große Bildschirme können wir fixed layout verwenden */
  }
  
  .btn-action {
    font-size: 0.875rem;
  }
  
  /* Optional: Horizontale Button-Anordnung für sehr breite Bildschirme */
  @media (min-width: 1600px) {
    .button-container {
      flex-direction: row;
    }
  }
}

/* Stilvolle Farbanpassungen für Hover und Active-Zustände */
.btn-action:hover {
  background-color: #42b883;
  transform: translateY(-1px);
}

.btn-action:active {
  transform: translateY(1px);
}

/* Optimierungen für besseren Kontrast bei dunkleren Themen */
@media (prefers-color-scheme: dark) {
  .streamer-table th {
    background-color: rgba(0, 0, 0, 0.4);
  }
  
  .btn-action:first-child {
    background-color: rgba(66, 184, 131, 0.6);
  }
  
  .btn-action:first-child:hover {
    background-color: rgba(66, 184, 131, 0.8);
  }
  
  .btn-action:last-child {
    background-color: rgba(220, 53, 69, 0.6);
  }
  
  .btn-action:last-child:hover {
    background-color: rgba(220, 53, 69, 0.8);
  }
}

/* Tabellen-Verbesserung für erhöhte Barrierefreiheit */
.no-streamers-message {
  padding: 1rem;
  text-align: center;
  color: #999;
}

.active-recordings {
  margin-top: 2rem;
}

.recordings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.recording-card {
  border: 1px solid #303034; /* Dark border matching theme */
  border-radius: 0.5rem;
  padding: 1rem;
  background-color: #1f1f23; /* Dark background matching theme */
  color: #efeff1; /* Light text matching theme */
}

.recording-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.recording-indicator {
  background-color: #dc3545;
  color: white;
  padding: 0.2rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.8rem;
  font-weight: bold;
}

.recording-details {
  margin-bottom: 1rem;
  color: #adadb8; /* Secondary text color matching theme */
}

.output-path {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  word-break: break-all;
  color: #adadb8; /* Secondary text color matching theme */
}

/* Override any styles that might be causing the light background */
.recording-card, .streamer-table {
  background-color: #1f1f23 !important; /* Important to override any conflicting styles */
  color: #efeff1 !important;
}

.variables-list {
  margin-top: 0.5rem;
  font-size: 0.9rem;
}

.variables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.variable-item {
  font-size: 0.85rem;
}

.filename-preview {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background-color: #343a40;
  border-radius: 0.25rem;
  font-size: 0.9rem;
  word-break: break-all;
  color: #f8f9fa;
  border: 1px solid #495057;
}

.streamer-settings {
  margin-top: 2rem;
}

.help-text {
  font-size: 0.85rem;
  color: #666;
  margin-top: 0.25rem;
}

.checkbox-group label {
  display: flex;
  align-items: flex-start;
  font-weight: normal;
  text-align: left;
}

.checkbox-group input[type="checkbox"] {
  margin-right: 8px;
  margin-top: 4px;
}

.loading-message, .error-message {
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: 0.25rem;
}

.loading-message {
  background-color: #1f1f23;
  color: #adadb8;
}

.error-message {
  background-color: rgba(220, 53, 69, 0.2); 
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.3);
}

.streamer-info {
  display: flex;
  align-items: center;
}

.streamer-avatar {
  width: 30px;
  height: 30px;
  margin-right: 10px;
  overflow: hidden;
  border-radius: 50%;
}

.streamer-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.table-controls {
  margin-bottom: 1rem;
}

.table-controls button {
  margin-right: 0.5rem;
}

.streamer-table {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  background-color: #1f1f23;
  border-radius: 6px;
  border: 1px solid #303034;
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
  border-bottom: 1px solid #303034;
  vertical-align: middle;
  text-align: left;
}

.streamer-table th:nth-child(1),
.streamer-table td:nth-child(1) {
  width: 35%;
}

.streamer-table th:nth-child(2),
.streamer-table td:nth-child(2) {
  width: 15%;
  text-align: center;
}

.streamer-table th:nth-child(3),
.streamer-table td:nth-child(3) {
  width: 20%;
}

.streamer-table th:nth-child(4),
.streamer-table td:nth-child(4) {
  width: 30%;
}

.th-tooltip {
  font-size: 0.75rem;
  font-weight: normal;
  color: #adadb8;
  margin-top: 0.25rem;
}

.settings-form {
  margin-bottom: 30px;
  background-color: #1f1f23;
  padding: 20px;
  border-radius: 8px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.form-control {
  width: 100%;
  padding: 10px;
  border: 1px solid #333;
  background-color: #18181b;
  color: #fff;
  border-radius: 4px;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
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
  background-color: #dc3545;
  color: white;
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
</style>