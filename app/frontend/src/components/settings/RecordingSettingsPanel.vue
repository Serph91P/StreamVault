<template>
    
    <div v-if="isLoading" class="loading-message">
      Loading recording settings...
    </div>
    
    <div v-else-if="error" class="error-message">
      Error loading settings: {{ error }}    
    </div>
      <!-- Tab Navigation -->
      <div class="tab-navigation">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="['tab-button', { active: activeTab === tab.id }]"
        >
          <svg v-if="tab.id === 'recording'" class="tab-icon">
            <use href="#icon-video" />
          </svg>
          <svg v-else-if="tab.id === 'storage'" class="tab-icon">
            <use href="#icon-server" />
          </svg>
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">        <!-- Recording Tab -->
        <div v-if="activeTab === 'recording'" class="tab-panel">
          <!-- Basic Recording Settings Section -->
          <div class="panel-block">
            <div class="section-header">
              <svg class="section-icon">
                <use href="#icon-video" />
              </svg>
              <h4 class="section-title">Basic Recording Settings</h4>
            </div>
            
            <div class="form-group">
              <label>
                <input type="checkbox" v-model="data.enabled" />
                Enable Recording
              </label>
              <div class="help-text">
                Master toggle for all recording functionality. When disabled, no streams will be recorded regardless of individual streamer settings.
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
                Default quality setting for new streamers. Individual streamers can override this setting.
              </div>
            </div>

            <div class="form-group">
              <label>Filename Template:</label>              
              <select v-model="data.filename_preset" class="form-control" @change="updateFilenameFromPreset" :disabled="presetsLoading">
                <option value="" v-if="presetsLoading">Loading presets...</option>
                <option v-for="preset in FILENAME_PRESETS" :key="preset.value" :value="preset.value">
                  {{ preset.label }}
                </option>
              </select>
              <div v-if="presetsError" class="error-text">
                Failed to load presets: {{ presetsError }}
              </div>
              <input ref="filenameTemplateInput" v-model="data.filename_template" class="form-control" style="margin-top: 10px;" />
              <div class="help-text">
                Choose a preset or customize the filename template.
                <br><strong>Available variables (click to insert):</strong>
                <div class="variables-container">
                  <button 
                    v-for="variable in FILENAME_VARIABLES" 
                    :key="variable.key" 
                    @click="insertVariable(variable.key)"
                    class="variable-tag clickable"
                    type="button"
                    :title="`Insert ${variable.key} - ${variable.description}`"
                  >
                    {{ variable.key }}
                  </button>
                </div>
                <br><br><strong>Example output: </strong>
                <code class="example-output">Streamername - S202506E01 - Just Chatting Stream.mp4</code>
                <br><small>Episode numbers (E01, E02, E03) are based on stream order within the month, not date.</small>
                <br><br><strong>💡 Advanced formatting:</strong>
                <br><small>Use <code>{episode:02d}</code> to format numbers with leading zeros (01, 02, 03...)
                <br>Use <code>{episode}</code> for simple numbers without padding (1, 2, 3...)</small>
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

            <!-- Codec Preferences (H.265/AV1 Support - Streamlink 8.0.0+) -->
            <div class="section-header" style="margin-top: 2rem;">
              <svg class="section-icon">
                <use href="#icon-settings" />
              </svg>
              <h4 class="section-title">Advanced Codec Settings</h4>
            </div>
            <div class="form-group">
              <label>Supported Codecs:</label>
              <select v-model="data.supported_codecs" class="form-control">
                <option value="h264">📺 H.264 Only - 1080p60 max, highest compatibility</option>
                <option value="h265">🎬 H.265/HEVC Only - 1440p60, modern hardware required</option>
                <option value="av1">🚀 AV1 Only - Experimental, newest hardware required</option>
                <option value="h264,h265">⭐ H.264 + H.265 (RECOMMENDED) - Best balance, auto-fallback</option>
                <option value="h264,h265,av1">🔮 All Codecs (Future-proof) - Maximum quality</option>
              </select>
              <div class="help-text">
                Configure video codec support for higher quality recordings (up to 1440p60).
                <br><br><strong>ℹ️ Important Notes:</strong>
                <ul style="margin-top: 0.5rem; margin-bottom: 0;">
                  <li>Higher quality streams depend on <strong>broadcaster settings</strong> (not all streamers support H.265/AV1)</li>
                  <li>Most channels still stream in H.264 only</li>
                  <li>H.265/AV1 decode requires modern hardware (2020+) and compatible players</li>
                  <li>If broadcaster doesn't support selected codec, Streamlink will auto-fallback to available codec</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- Storage Tab -->
        <div v-if="activeTab === 'storage'" class="tab-panel">
          <div class="panel-block">
            <div class="section-header">
              <svg class="section-icon">
                <use href="#icon-server" />
              </svg>
              <h4 class="section-title">Storage & Cleanup Management</h4>
            </div>
            <p class="section-description">
              Configure automatic cleanup policies to manage storage space and organize your recordings efficiently.
            </p>
            
            <CleanupPolicyEditor
              :is-global="true"
              title="Global Cleanup Policy"
              @saved="handleCleanupPolicySaved"
            />
          </div>
        </div>
      </div>

      <!-- Save Button (outside of tabs) -->
      <div class="form-actions">
        <button @click="saveSettings" class="btn btn-primary" :disabled="isSaving">
          {{ isSaving ? 'Saving...' : 'Save Settings' }}        </button>
      </div>

    <!-- Active Recordings -->
    <div v-if="activeRecordings.length > 0" class="active-recordings panel-block">
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
            <div><strong>Status:</strong> {{ recording.status }}</div>
            <div class="output-path"><strong>Output:</strong> {{ recording.file_path || recording.output_path }}</div>
          </div>
          <button @click="stopRecording(recording.streamer_id)" class="btn btn-danger" :disabled="isLoading">
            Stop Recording
          </button>
        </div>
      </div>
    </div>
    <!-- Streamer Settings -->
    <div class="streamer-settings panel-block">
      <h3>Streamer Recording Settings</h3>
      
      <div v-if="!streamerSettings || streamerSettings.length === 0" class="no-streamers-message">
        <p>No streamers found. Add streamers in the Streamers section to configure recording settings.</p>
      </div>
        <template v-else>
        <div class="table-controls">
          <button @click="toggleAllStreamers(true)" class="btn btn-secondary">Enable All</button>
          <button @click="toggleAllStreamers(false)" class="btn btn-secondary">Disable All</button>
        </div>

        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Streamer</th>
                <th>
                  <span class="th-content">
                    Record
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Enable/disable recording for this streamer</span>
                      </span>
                    </span>
                  </span>
                </th>
                <th>
                  <span class="th-content">
                    Quality
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Select recording quality (defaults to global setting if empty)</span>
                      </span>
                    </span>
                  </span>
                </th>
                <th>
                  <span class="th-content">
                    Custom Filename
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Optional custom filename template for this streamer</span>
                      </span>
                    </span>
                  </span>
                </th>
                <th>
                  <span class="th-content">
                    Actions
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Test, stop, or clean up recordings</span>
                      </span>
                    </span>
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="streamer in streamerSettings" :key="streamer.streamer_id">
                <td class="streamer-info" data-label="">
                  <div class="streamer-avatar" v-if="streamer.profile_image_url">
                    <img :src="streamer.profile_image_url" :alt="streamer.username || ''" />
                  </div>
                  <span class="streamer-name">{{ streamer.username || 'Unknown Streamer' }}</span>
                </td>
                <td data-label="Record">
                  <input type="checkbox" v-model="streamer.enabled"
                    @change="updateStreamerSetting(streamer.streamer_id, { enabled: streamer.enabled })" />
                </td>
                <td data-label="Quality">
                  <select v-model="streamer.quality"
                    @change="updateStreamerSetting(streamer.streamer_id, { quality: streamer.quality })"
                    class="form-control form-control-sm">
                    <option value="">Use global default</option>
                    <option v-for="option in QUALITY_OPTIONS" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </td>
                <td data-label="Custom Filename">
                  <input type="text" v-model="streamer.custom_filename"
                    @change="updateStreamerSetting(streamer.streamer_id, { custom_filename: streamer.custom_filename })"
                    placeholder="Use global template" class="form-control form-control-sm" />
                </td>
                <td data-label="Actions" class="actions-cell">
                  <div class="actions-group">
                    <button 
                      v-if="isActiveRecording(streamer.streamer_id)" 
                      @click="stopRecording(streamer.streamer_id)" 
                      class="btn btn-danger btn-sm" 
                      :disabled="isLoading">
                      Stop
                    </button>
                    <button 
                      @click="openCleanupPolicyEditor(streamer)" 
                      class="btn btn-info btn-sm" 
                      :disabled="isLoading"
                      title="Configure cleanup policy for this streamer">
                      Policy
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
    
    <!-- Per-Streamer Cleanup Policy Editor Dialog -->
    <div v-if="showStreamerPolicyDialog" class="modal-overlay" @click="closeStreamerPolicyDialog">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Cleanup Policy for {{ selectedStreamer?.username || 'Streamer' }}</h3>
          <button @click="closeStreamerPolicyDialog" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <CleanupPolicyEditor
            v-if="selectedStreamer"
            :streamer-id="selectedStreamer.streamer_id"
            :title="`Cleanup Policy for ${selectedStreamer.username}`"
            :is-global="false"
            @saved="handleStreamerPolicySaved"
          />
        </div>
      </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { useFilenamePresets } from '@/composables/useFilenamePresets';
import { useToast } from '@/composables/useToast';
import { QUALITY_OPTIONS, FILENAME_VARIABLES } from '@/types/recording';
import type { RecordingSettings, StreamerRecordingSettings } from '@/types/recording';
import type { GlobalSettings } from '@/types/settings';
import CleanupPolicyEditor from '@/components/CleanupPolicyEditor.vue';
import GlassCard from '@/components/cards/GlassCard.vue';

const props = defineProps<{
  settings: RecordingSettings | null;
  streamerSettings: StreamerRecordingSettings[];
  activeRecordings: any[];
}>();

const emits = defineEmits<{
  update: [settings: RecordingSettings];
  updateStreamer: [streamerId: number, settings: Partial<StreamerRecordingSettings>];
  stopRecording: [streamerId: number];
}>();

// Tab management
const activeTab = ref('recording');
const tabs = [
  { id: 'recording', label: 'Recording' },
  { id: 'storage', label: 'Storage' }
];

const { isLoading, error } = useRecordingSettings();
const toast = useToast();

// Filename presets from API
const { presets: FILENAME_PRESETS, isLoading: presetsLoading, error: presetsError } = useFilenamePresets();

// State for streamer cleanup policy dialog
const showStreamerPolicyDialog = ref(false);
const selectedStreamer = ref<StreamerRecordingSettings | null>(null);

// Function to detect preset from template
const detectPresetFromTemplate = (template: string): string => {
  const preset = FILENAME_PRESETS.find((p: any) => p.description === template);
  return preset ? preset.value : 'default';
};

// Create a copy of the settings for editing
const filenameTemplateInput = ref<HTMLInputElement | null>(null);
const data = ref<RecordingSettings>({
  enabled: props.settings?.enabled ?? false,
  filename_template: props.settings?.filename_template ?? '{streamer}/{streamer}_{year}{month}-{day}_{hour}-{minute}_{title}_{game}',
  filename_preset: props.settings?.filename_preset || detectPresetFromTemplate(props.settings?.filename_template ?? ''),
  default_quality: props.settings?.default_quality ?? 'best',
  use_chapters: props.settings?.use_chapters ?? true,
  use_category_as_chapter_title: props.settings?.use_category_as_chapter_title ?? false,
  // Codec preferences (Migration 024) - H.265/AV1 Support
  supported_codecs: props.settings?.supported_codecs || 'h264,h265',
  prefer_higher_quality: props.settings?.prefer_higher_quality !== false
});

const updateFilenameTemplate = () => {
  const preset = FILENAME_PRESETS.find((p: any) => p.value === data.value.filename_preset);
  if (preset) {
    data.value.filename_template = preset.description;
  }
};

// Update local data when props change
watch(() => props.settings, (newSettings: RecordingSettings | null) => {
  if (newSettings) {
    data.value = { 
      ...newSettings, 
      filename_preset: newSettings.filename_preset || detectPresetFromTemplate(newSettings.filename_template ?? '')
    };
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

// Update filename template when preset changes
const updateFilenameFromPreset = () => {
  const selectedPreset = FILENAME_PRESETS.find((preset: any) => preset.value === data.value.filename_preset);
  if (selectedPreset) {
    data.value.filename_template = selectedPreset.description;
  }
};

// Function to insert variable at cursor position
const insertVariable = (variableKey: string) => {
  const currentTemplate = data.value.filename_template || '';
  const inputElement = filenameTemplateInput.value;
  
  // Get the actual cursor position from the input element
  let cursorPosition = currentTemplate.length; // Default to end
  if (inputElement && typeof inputElement.selectionStart === 'number') {
    cursorPosition = inputElement.selectionStart;
  }
  
  // Insert the variable at the cursor position
  const newTemplate = currentTemplate.slice(0, cursorPosition) + variableKey + currentTemplate.slice(cursorPosition);
  data.value.filename_template = newTemplate;
  
  // Update the preset to "custom" when manually adding variables
  data.value.filename_preset = 'custom';
  
  // Focus back to input and set cursor position after the inserted variable
  if (inputElement) {
    inputElement.focus();
    const newCursorPosition = cursorPosition + variableKey.length;
    // Use nextTick to ensure the value is updated in the DOM
    nextTick(() => {
      inputElement.setSelectionRange(newCursorPosition, newCursorPosition);
    });
  }
};

const saveSettings = async () => {
  try {
    isSaving.value = true;
    
    // Save recording settings
    emits('update', {
      enabled: data.value.enabled,
      filename_template: data.value.filename_template,
      filename_preset: data.value.filename_preset,
      default_quality: data.value.default_quality,
      use_chapters: data.value.use_chapters,
      use_category_as_chapter_title: data.value.use_category_as_chapter_title,
      // Codec preferences (Migration 024)
      supported_codecs: data.value.supported_codecs,
      prefer_higher_quality: data.value.prefer_higher_quality
    });
    
  } catch (error) {
    console.error('Failed to save settings:', error);
    toast.error('Failed to save settings. Please try again.');
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

const isActiveRecording = (streamerId: number): boolean => {
  return props.activeRecordings.some((rec: any) => rec.streamer_id === streamerId);
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

// Methods for per-streamer cleanup policy editor
const openCleanupPolicyEditor = (streamer: StreamerRecordingSettings) => {
  selectedStreamer.value = streamer;
  showStreamerPolicyDialog.value = true;
};

const closeStreamerPolicyDialog = () => {
  showStreamerPolicyDialog.value = false;
  selectedStreamer.value = null;
};

const handleStreamerPolicySaved = (policy: any) => {
  
  closeStreamerPolicyDialog();
};
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.settings-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-7, 28px);
}

.panel-block {
  padding: var(--spacing-6, 24px);
  border-radius: var(--radius-xl, 32px);
  background: transparent;
}

/* Section Headers with Icons */
.section-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3, 12px);
  margin-bottom: var(--spacing-5, 20px);
}

.section-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  color: var(--primary-color);
}

.section-title {
  font-size: var(--text-lg, 18px);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.section-description {
  font-size: var(--text-sm, 14px);
  color: var(--text-secondary);
  margin: var(--spacing-2, 8px) 0 var(--spacing-4, 16px) 0;
  line-height: 1.6;
}

/* Tab Navigation Styles */
.tab-navigation {
  display: flex;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: var(--spacing-8, 32px);
  gap: var(--spacing-2, 8px);
}

.tab-button {
  display: flex;
  align-items: center;
  gap: var(--spacing-2, 8px);
  background: transparent;
  border: none;
  padding: var(--spacing-4) var(--spacing-6);
  cursor: pointer;
  color: var(--text-secondary);
  font-weight: 600;
  font-size: var(--text-base, 16px);
  border-radius: var(--radius-lg, 12px) var(--radius-lg, 12px) 0 0;
  transition: all 0.2s ease;
  border-bottom: 3px solid transparent;
  position: relative;

  .tab-icon {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
  }
}

.tab-button:hover:not(.active) {
  background-color: rgba(var(--primary-color-rgb), 0.05);
  color: var(--text-primary);
}

.tab-button.active {
  background-color: rgba(var(--primary-color-rgb), 0.1);
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  
  .tab-icon {
    color: var(--primary-color);
  }
}

.tab-content {
  min-height: 300px;
}

.tab-panel {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Mobile-First-Ansatz - Basis-Styles für mobile Geräte */

.settings-form,
.active-recordings,
.streamer-settings {
  margin-bottom: 0;
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
  padding: var(--spacing-3);
  border: 1px solid var(--border-color);
  background-color: var(--background-dark, #18181b);
  color: var(--text-primary, #f1f1f3);
  border-radius: var(--border-radius);
  box-sizing: border-box;
}

/* Error state for form controls */
.form-control.error {
  border-color: var(--danger-color);
  background-color: rgba(239, 68, 68, 0.1);
}

// ============================================================================
// CODEC SELECTION - Component specific
// ============================================================================

.codec-selection {
  display: flex;
  gap: v.$spacing-2;
  flex-wrap: wrap;
  
  label {
    display: flex;
    align-items: center;
    gap: v.$spacing-2;
    padding: v.$spacing-2 v.$spacing-3;
    background: var(--background-card);
    border: 2px solid var(--border-color);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: v.$transition-all;
    
    &:hover {
      border-color: var(--primary-color);
      background: var(--background-hover);
    }
    
    input[type="checkbox"] {
      margin: 0;
    }
    
    &:has(input:checked) {
      border-color: var(--primary-color);
      background: var(--primary-bg);
      color: var(--primary-color);
      font-weight: v.$font-medium;
    }
  }
}

// ============================================================================
// ACTIVE RECORDINGS SECTION
// ============================================================================

.active-recordings-list {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-4;
}

.recording-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: v.$spacing-4;
  background: var(--background-hover);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: v.$transition-all;
  
  &:hover {
    border-color: var(--primary-color);
  }
  
  @include m.respond-below('md') {
    flex-direction: column;
    gap: v.$spacing-3;
    align-items: flex-start;
  }
}

.recording-info {
  flex: 1;
  
  .streamer-name {
    font-weight: v.$font-semibold;
    color: var(--text-primary);
    font-size: v.$text-base;
  }
  
  .recording-meta {
    font-size: v.$text-sm;
    color: var(--text-secondary);
    margin-top: v.$spacing-1;
  }
}

.recording-actions {
  display: flex;
  gap: v.$spacing-2;
  
  @include m.respond-below('md') {
    width: 100%;
    justify-content: flex-end;
  }
}

// ============================================================================
// STREAMER SETTINGS TABLE
// ============================================================================

.streamer-table {
  width: 100%;
  border-collapse: collapse;
  
  thead {
    background: var(--background-hover);
    
    th {
      padding: v.$spacing-3;
      text-align: left;
      font-weight: v.$font-semibold;
      color: var(--text-primary);
      border-bottom: 2px solid var(--border-color);
      
      @include m.respond-below('md') {
        display: none;
      }
    }
  }
  
  tbody {
    tr {
      border-bottom: 1px solid var(--border-color);
      transition: v.$transition-colors;
      
      &:hover {
        background: var(--background-hover);
      }
      
      @include m.respond-below('md') {
        display: block;
        margin-bottom: v.$spacing-4;
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: v.$spacing-3;
      }
    }
    
    td {
      padding: v.$spacing-3;
      color: var(--text-primary);
      
      @include m.respond-below('md') {
        display: block;
        text-align: right;
        padding: v.$spacing-2 0;
        border: none;
        
        &:before {
          content: attr(data-label);
          float: left;
          font-weight: v.$font-semibold;
          color: var(--text-secondary);
        }
      }
    }
  }
}

// ============================================================================
// PROXY CONFIGURATION (if present in this panel)
// ============================================================================

.proxy-configuration {
  .proxy-info-card {
    background: var(--info-bg-color);
    border: 1px solid var(--info-border-color);
    border-radius: var(--radius-md);
    padding: v.$spacing-4;
    margin-bottom: v.$spacing-4;
    
    h5, h6 {
      color: var(--text-primary);
      margin-bottom: v.$spacing-2;
    }
    
    h5 {
      font-size: v.$text-base;
      font-weight: v.$font-semibold;
    }
    
    h6 {
      font-size: v.$text-sm;
      font-weight: v.$font-medium;
    }
  }
  
  .proxy-examples-list,
  .proxy-tips {
    list-style: none;
    padding: 0;
    
    li {
      padding: v.$spacing-2 0;
      color: var(--text-secondary);
      font-size: v.$text-sm;
      
      code {
        background: var(--background-darker);
        padding: v.$spacing-1 v.$spacing-2;
        border-radius: var(--radius-sm);
        font-family: var(--font-mono);
        font-size: v.$text-xs;
        color: var(--primary-color);
      }
    }
  }
  
  .example-item {
    padding: v.$spacing-3;
    margin-bottom: v.$spacing-2;
    background: var(--background-card);
    border-radius: var(--radius-sm);
    
    code {
      display: block;
      word-break: break-all;
      margin-top: v.$spacing-1;
    }
  }
}

// ============================================================================
// TABLE HEADER TOOLTIPS
// ============================================================================

.th-content {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1, 4px);
}

.th-tooltip-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  
  &:hover .tooltip-wrapper {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
  }
  
  .tooltip-wrapper {
    position: absolute;
    top: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%) translateY(-4px);
    z-index: 1000;
    opacity: 0;
    visibility: hidden;
    transition: all v.$duration-200 v.$ease-out;
    pointer-events: none;
    white-space: nowrap;
    
    .tooltip {
      display: block;
      padding: var(--spacing-2, 8px) var(--spacing-3, 12px);
      background: var(--background-darker);
      color: var(--text-primary);
      font-size: var(--text-xs, 12px);
      border-radius: var(--radius, 8px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-color);
      font-weight: normal;
      text-transform: none;
      letter-spacing: normal;
      max-width: 250px;
      white-space: normal;
      line-height: 1.4;
      
      // Light mode: Better contrast
      [data-theme="light"] & {
        background: var(--background-card);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        border-color: var(--border-color);
      }
      
      // Arrow
      &::before {
        content: '';
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        border: 6px solid transparent;
        border-bottom-color: var(--background-darker);
        
        [data-theme="light"] & {
          border-bottom-color: var(--background-card);
        }
      }
    }
  }
}

// ============================================================================
// RESPONSIVE MOBILE OPTIMIZATIONS
// ============================================================================

@include m.respond-below('md') {
  .tab-navigation {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    gap: v.$spacing-1;
    margin-bottom: v.$spacing-4;
    padding-bottom: v.$spacing-2;
    
    &::-webkit-scrollbar {
      height: 4px;
    }
    
    &::-webkit-scrollbar-thumb {
      background: var(--border-color);
      border-radius: 2px;
    }
  }
  
  .tab-button {
    min-width: 140px;  // Increased to show full text
    flex-shrink: 0;
    padding: v.$spacing-3 v.$spacing-4;
    font-size: v.$text-sm;
    white-space: nowrap;  // Prevent text wrapping
    
    .tab-icon {
      width: 18px;
      height: 18px;
    }
  }
  
  .form-actions {
    flex-direction: column;
    gap: v.$spacing-3;
    
    .btn {
      width: 100%;
    }
  }
}

@include m.respond-below('xs') {
  .variable-tag {
    font-size: v.$text-xs;
    padding: v.$spacing-1 v.$spacing-2;
  }
  
  .section-title {
    font-size: v.$text-base;
  }
}
</style>
