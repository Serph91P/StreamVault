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
      <!-- Tab Navigation -->
      <div class="tab-navigation">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="['tab-button', { active: activeTab === tab.id }]"
        >
          {{ tab.icon }} {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">        <!-- Recording Tab -->
        <div v-if="activeTab === 'recording'" class="tab-panel">
          <!-- Basic Recording Settings Section -->
          <div class="settings-section">
            <h4 class="section-title">📹 Basic Recording Settings</h4>
            
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
              <label>Output Directory:</label>
              <input v-model="data.output_directory" class="form-control" />
              <div class="help-text">
                Base directory where recordings will be saved. Individual streamers will have subdirectories created here.
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
              <input v-model="data.filename_template" class="form-control" style="margin-top: 10px;" />
              <div class="help-text">
                Choose a preset or customize the filename template.
                <br><strong>Available variables:</strong>
                <div class="variables-container">
                  <span v-for="variable in FILENAME_VARIABLES" :key="variable.key" class="variable-tag">
                    {{ variable.key }}
                  </span>
                </div>
                <br><br><strong>Example output: </strong>
                <code class="example-output">Streamername - S202506E01 - Just Chatting Stream.mp4</code>
                <br><small>Episode numbers (E01, E02, E03) are based on stream order within the month, not date.</small>
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
          </div>
        </div>

        <!-- Network Tab -->
        <div v-if="activeTab === 'network'" class="tab-panel">
          <div class="settings-section">
            <h4 class="section-title">🌐 Network & Proxy Settings</h4>
            <p class="section-description">
              Configure proxy settings for Streamlink to route traffic through different locations. 
              This can help reduce ads if using a proxy in a region with fewer advertisements.
            </p>
              <div class="form-group">
              <label>
                <input type="checkbox" v-model="proxySettings.enabled" />
                Enable Proxy Settings
              </label>
              <div class="help-text">
                When enabled, Streamlink will use the configured proxy servers for all connections.
                <br><strong>⚠️ Note:</strong> Proxy usage may occasionally cause audio synchronization issues due to network latency. 
                StreamVault includes optimizations to minimize these issues, but you may need to test different proxy servers for best results.
              </div>
            </div>

            <div v-if="proxySettings.enabled" class="proxy-configuration">
              <div class="form-group">
                <label>HTTP Proxy:</label>
                <input v-model="proxySettings.http_proxy" 
                       placeholder="http://proxy.example.com:8080" 
                       class="form-control" 
                       :class="{ 'error': httpProxyError }" />
                <div v-if="httpProxyError" class="error-text">
                  {{ httpProxyError }}
                </div>
                <div class="help-text">
                  HTTP proxy server for non-encrypted connections.
                  <br><strong>Format:</strong> <code>http://[username:password@]host:port</code>
                </div>
              </div>

              <div class="form-group">
                <label>HTTPS Proxy:</label>
                <input v-model="proxySettings.https_proxy" 
                       placeholder="https://proxy.example.com:8080" 
                       class="form-control" 
                       :class="{ 'error': httpsProxyError }" />
                <div v-if="httpsProxyError" class="error-text">
                  {{ httpsProxyError }}
                </div>
                <div class="help-text">
                  HTTPS proxy server for encrypted connections (recommended for Twitch).
                  <br><strong>Format:</strong> <code>https://[username:password@]host:port</code>
                </div>
              </div>

              <div class="proxy-examples">
                <h5>📋 Proxy URL Examples:</h5>
                <ul>
                  <li><code>http://proxy.example.com:8080</code> - Basic proxy</li>
                  <li><code>http://username:password@proxy.example.com:8080</code> - Authenticated proxy</li>
                  <li><code>https://secure-proxy.example.com:8080</code> - HTTPS proxy</li>
                  <li><code>socks5://127.0.0.1:1080</code> - SOCKS5 proxy (if supported)</li>
                </ul>
              </div>
                <div class="proxy-tips">
                <h6>💡 Tips:</h6>
                <ul>
                  <li>Use HTTPS proxy for better security and compatibility with Twitch</li>
                  <li>Test your proxy configuration before enabling recording</li>
                  <li>Some regions have fewer or no Twitch advertisements</li>
                  <li>Ensure your proxy provider allows video streaming traffic</li>
                  <li>Leave fields empty to disable proxy for that protocol</li>
                  <li><strong>Audio Sync:</strong> If you experience audio/video sync issues, try a different proxy server or disable proxy temporarily</li>
                  <li><strong>Performance:</strong> StreamVault automatically optimizes settings for proxy usage, but some latency is expected</li>
                </ul>
              </div>
            </div>
          </div>
        </div>        <!-- Storage Tab -->
        <div v-if="activeTab === 'storage'" class="tab-panel">
          <div class="settings-section">
            <h4 class="section-title">🗂️ Storage & Cleanup Management</h4>
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
      </div>    </div>

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
                  <div class="streamer-actions">
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { useFilenamePresets } from '@/composables/useFilenamePresets';
import { QUALITY_OPTIONS, FILENAME_VARIABLES } from '@/types/recording';
import type { RecordingSettings, StreamerRecordingSettings } from '@/types/recording';
import type { GlobalSettings } from '@/types/settings';
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
}>();

// Tab management
const activeTab = ref('recording');
const tabs = [
  { id: 'recording', label: 'Recording', icon: '📹' },
  { id: 'network', label: 'Network', icon: '🌐' },
  { id: 'storage', label: 'Storage', icon: '🗂️' }
];

const { isLoading, error } = useRecordingSettings();

// Filename presets from API
const { presets: FILENAME_PRESETS, isLoading: presetsLoading, error: presetsError } = useFilenamePresets();

// State for streamer cleanup policy dialog
const showStreamerPolicyDialog = ref(false);
const selectedStreamer = ref<StreamerRecordingSettings | null>(null);

// Proxy settings state
const proxySettings = ref({
  enabled: false,
  http_proxy: '',
  https_proxy: ''
});

// Computed properties for real-time validation
const httpProxyError = computed(() => {
  if (!proxySettings.value.enabled || !proxySettings.value.http_proxy.trim()) {
    return '';
  }
  if (!validateProxyUrl(proxySettings.value.http_proxy)) {
    return 'HTTP proxy URL must start with "http://" or "https://"';
  }
  return '';
});

const httpsProxyError = computed(() => {
  if (!proxySettings.value.enabled || !proxySettings.value.https_proxy.trim()) {
    return '';
  }
  if (!validateProxyUrl(proxySettings.value.https_proxy)) {
    return 'HTTPS proxy URL must start with "http://" or "https://"';
  }
  return '';
});

// Check if proxy settings have validation errors
const hasProxyErrors = computed(() => {
  return httpProxyError.value !== '' || httpsProxyError.value !== '';
});

// Load proxy settings from GlobalSettings API
const loadProxySettings = async () => {
  try {
    const response = await fetch('/api/settings');
    if (response.ok) {
      const globalSettings: GlobalSettings = await response.json();
      proxySettings.value = {
        enabled: !!(globalSettings.http_proxy || globalSettings.https_proxy),
        http_proxy: globalSettings.http_proxy || '',
        https_proxy: globalSettings.https_proxy || ''
      };
    }
  } catch (error) {
    console.error('Failed to load proxy settings:', error);
  }
};

// Validate proxy URL format
const validateProxyUrl = (url: string): boolean => {
  if (!url || !url.trim()) {
    return true; // Empty URLs are valid (no proxy)
  }
  
  const trimmedUrl = url.trim();
  return trimmedUrl.startsWith('http://') || trimmedUrl.startsWith('https://');
};

// Save proxy settings to GlobalSettings API
const saveProxySettings = async () => {
  try {
    // Check for validation errors before attempting to save
    if (hasProxyErrors.value) {
      // Don't save if there are validation errors - the errors are already shown in the UI
      return;
    }
    
    const response = await fetch('/api/settings');
    if (!response.ok) throw new Error('Failed to load current settings');
    
    const globalSettings: GlobalSettings = await response.json();
    
    // Update proxy fields
    const updatedSettings = {
      ...globalSettings,
      http_proxy: proxySettings.value.enabled ? proxySettings.value.http_proxy : '',
      https_proxy: proxySettings.value.enabled ? proxySettings.value.https_proxy : ''
    };
    
    const saveResponse = await fetch('/api/settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatedSettings),
    });
    
    if (!saveResponse.ok) {
      throw new Error('Failed to save proxy settings');
    }
    
    console.log('Proxy settings saved successfully');
  } catch (error) {
    console.error('Failed to save proxy settings:', error);
    alert('Failed to save proxy settings. Please try again.');
  }
};

// Load proxy settings on component mount
onMounted(() => {
  loadProxySettings();
});

// Function to detect preset from template
const detectPresetFromTemplate = (template: string): string => {
  const preset = FILENAME_PRESETS.find((p: any) => p.description === template);
  return preset ? preset.value : 'default';
};

// Create a copy of the settings for editing
const data = ref<RecordingSettings>({
  enabled: props.settings?.enabled ?? false,
  output_directory: props.settings?.output_directory ?? '/recordings',
  filename_template: props.settings?.filename_template ?? '{streamer}/{streamer}_{year}{month}-{day}_{hour}-{minute}_{title}_{game}',
  filename_preset: props.settings?.filename_preset || detectPresetFromTemplate(props.settings?.filename_template ?? ''),
  default_quality: props.settings?.default_quality ?? 'best',
  use_chapters: props.settings?.use_chapters ?? true,
  use_category_as_chapter_title: props.settings?.use_category_as_chapter_title ?? false
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

const saveSettings = async () => {
  try {
    isSaving.value = true;
    
    // Save recording settings
    emits('update', {
      enabled: data.value.enabled,
      output_directory: data.value.output_directory,
      filename_template: data.value.filename_template,
      filename_preset: data.value.filename_preset,
      default_quality: data.value.default_quality,
      use_chapters: data.value.use_chapters,
      use_category_as_chapter_title: data.value.use_category_as_chapter_title
    });
    
    // Save proxy settings separately
    await saveProxySettings();
    
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
  console.log('Streamer cleanup policy saved:', policy);
  closeStreamerPolicyDialog();
};
</script>

<style scoped>
/* Tab Navigation Styles */
.tab-navigation {
  display: flex;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 24px;
  gap: 4px;
}

.tab-button {
  background: none;
  border: none;
  padding: 12px 20px;
  cursor: pointer;
  color: var(--text-secondary);
  font-weight: 500;
  border-radius: 6px 6px 0 0;
  transition: all 0.2s ease;
  border-bottom: 3px solid transparent;
  font-size: 14px;
}

.tab-button:hover {
  background-color: var(--background-dark);
  color: var(--text-primary);
}

.tab-button.active {
  background-color: var(--background-darker);
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
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

/* Error state for form controls */
.form-control.error {
  border-color: #ef4444;
  background-color: rgba(239, 68, 68, 0.1);
}

/* Error text styling */
.error-text {
  color: #ef4444;
  font-size: 0.875rem;
  margin-top: 4px;
  font-weight: 500;
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

.btn-info {
  background-color: var(--info-color, #17a2b8);
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

/* Modal styles for cleanup policy dialog */
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
  width: 800px;
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

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: var(--text-secondary, #adadb8);
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
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

.modal-body {
  padding: 20px;
}

/* Settings sections for better visual organization */
.settings-section {
  margin-bottom: var(--spacing-xxl, 2.5rem);
  padding: var(--spacing-lg, 1.5rem);
  background-color: rgba(0, 0, 0, 0.1);
  border-radius: var(--border-radius, 8px);
  border-left: 4px solid var(--primary-color, #42b883);
}

.settings-section:last-child {
  margin-bottom: var(--spacing-lg, 1.5rem);
}

.section-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary, #f1f1f3);
  margin-bottom: var(--spacing-md, 1rem);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 0.5rem);
}

.section-description {
  color: var(--text-secondary, #adadb8);
  margin-bottom: var(--spacing-lg, 1.5rem);  line-height: 1.6;
  font-size: 0.95rem;
}

/* Proxy settings specific styles */
.proxy-configuration {
  margin-top: var(--spacing-md, 1rem);
  padding: var(--spacing-lg, 1.5rem);
  background-color: rgba(0, 0, 0, 0.1);
  border-radius: var(--border-radius, 8px);
  border-left: 3px solid var(--info-color, #17a2b8);
}

.proxy-examples {
  margin-top: var(--spacing-lg, 1.5rem);
  padding: var(--spacing-md, 1rem);
  background-color: var(--background-dark, #18181b);
  border-radius: var(--border-radius, 6px);
  border: 1px solid var(--border-color, #303034);
}

.proxy-examples h5 {
  margin-bottom: var(--spacing-md, 1rem);
  color: var(--text-primary, #f1f1f3);
  font-size: 1rem;
  font-weight: 600;
}

.proxy-examples h6 {
  margin-top: var(--spacing-lg, 1.5rem);
  margin-bottom: var(--spacing-sm, 0.5rem);
  color: var(--text-primary, #f1f1f3);
  font-size: 0.9rem;
  font-weight: 600;
}

.example-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm, 0.5rem);
}

.example-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs, 0.25rem);
  padding: var(--spacing-sm, 0.5rem);
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: var(--border-radius-sm, 4px);
}

.example-item code {
  background-color: var(--background-darker, #1f1f23);
  color: var(--primary-color, #42b883);
  padding: 4px 8px;
  border-radius: var(--border-radius-sm, 4px);
  font-family: 'Courier New', monospace;
  font-size: 0.85rem;
  border: 1px solid var(--border-color, #303034);
  display: inline-block;
  word-break: break-all;
}

.example-item span {
  color: var(--text-secondary, #adadb8);
  font-size: 0.8rem;
  font-style: italic;
}

.proxy-tips {
  margin-top: var(--spacing-md, 1rem);
}

.proxy-tips ul {
  margin: var(--spacing-sm, 0.5rem) 0;
  padding-left: var(--spacing-lg, 1.5rem);
}

.proxy-tips li {
  color: var(--text-secondary, #adadb8);
  font-size: 0.85rem;
  line-height: 1.4;
  margin-bottom: var(--spacing-xs, 0.25rem);
}

/* Mobile responsiveness for proxy settings */
@media (max-width: 767px) {
  .proxy-configuration {
    padding: var(--spacing-md, 1rem);
  }
  
  .proxy-examples {
    padding: var(--spacing-sm, 0.75rem);
  }
  
  .example-item {
    padding: var(--spacing-xs, 0.375rem);
  }
  
  .example-item code {
    font-size: 0.75rem;
    padding: 3px 6px;
  }

  .variables-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0;
  }

  .variable-tag {
    display: inline-block;
    background-color: var(--background-dark, #2a2a2a);
    color: var(--text-primary, #f1f1f3);
    border: 1px solid var(--border-color, #404040);
    border-radius: 4px;
    padding: 4px 8px;
    font-family: 'Courier New', 'Monaco', monospace;
    font-size: 0.8em;
    font-weight: 500;
    white-space: nowrap;
  }

  .example-output {
    display: inline-block;
    background-color: var(--bg-tertiary, #2a2a2a);
    color: var(--accent-color, #4a9eff);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 4px 8px;
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
    font-weight: 600;
  }
}
</style>