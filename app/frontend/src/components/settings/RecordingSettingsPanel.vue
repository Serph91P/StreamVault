<template>

    <div v-if="isLoading" class="loading-message">
      Aufnahmeeinstellungen werden geladen...
    </div>

    <div v-else-if="error" class="error-message">
      Einstellungen konnten nicht geladen werden: {{ error }}
    </div>
      <!-- Recording and Storage are separate settings sections now; this
           component renders one half, selected via the `section` prop -->
      <div v-if="context === 'global'" class="tab-content">
        <div v-if="section === 'recording'" class="tab-panel">
          <!-- Basic Recording Settings Section -->
          <div class="panel-block">
            <div class="section-header">
              <svg class="section-icon">
                <use href="#icon-video" />
              </svg>
              <h3 class="section-title">Globale Aufnahmevorgaben</h3>
            </div>

            <div class="form-group">
              <label class="checkbox-target">
                <input type="checkbox" v-model="data.enabled" />
                Automatische Aufnahme aktivieren
              </label>
              <div class="help-text">
                Hauptschalter für Aufnahmen. Ausgeschaltet werden keine Streams aufgenommen, unabhängig von den Einstellungen einzelner Kanäle.
              </div>
            </div>

            <div class="form-group">
              <label>Standardqualität:</label>
              <select v-model="data.default_quality" class="form-control">
                <option v-for="option in QUALITY_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <div class="help-text">
                Standardqualität für neue Kanäle. Einzelne Kanäle können diese Vorgabe überschreiben.
              </div>
            </div>

            <div class="form-group">
              <label>Dateinamenvorlage:</label>
              <select v-model="data.filename_preset" class="form-control" @change="updateFilenameFromPreset" :disabled="presetsLoading">
                <option value="" v-if="presetsLoading">Vorlagen werden geladen...</option>
                <option v-for="preset in FILENAME_PRESETS" :key="preset.value" :value="preset.value">
                  {{ preset.label }}
                </option>
              </select>
              <div v-if="presetsError" class="error-text">
                Vorlagen konnten nicht geladen werden: {{ presetsError }}
              </div>
              <input ref="filenameTemplateInput" v-model="data.filename_template" class="form-control" style="margin-top: 10px;" />
              <div class="help-text">
                Eine Vorlage wählen oder die Dateinamenvorlage anpassen.
                <br><strong>Verfügbare Variablen (zum Einfügen anklicken):</strong>
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
                <br><br><strong>Beispiel: </strong>
                <code class="example-output">Streamername - S202506E01 - Just Chatting Stream.mp4</code>
                <br><small>Episodennummern (E01, E02, E03) folgen der Streamreihenfolge im Monat, nicht dem Datum.</small>
                <br><br><strong>Erweiterte Formatierung:</strong>
                <br><small><code>{episode:02d}</code> erzeugt führende Nullen (01, 02, 03...).
                <br><code>{episode}</code> erzeugt einfache Nummern (1, 2, 3...).</small>
              </div>
            </div>

            <div class="form-group">
              <label class="checkbox-target">
                <input type="checkbox" v-model="data.use_chapters" />
                Kapitel aus Streamereignissen erzeugen
              </label>
              <div class="help-text">
                Bei Titel- und Spielwechseln Kapitelmarken in der Aufnahme setzen.
              </div>
            </div>

            <div class="form-group">
              <label class="checkbox-target">
                <input type="checkbox" v-model="data.use_category_as_chapter_title" />
                Kategorie als Kapiteltitel verwenden
              </label>
              <div class="help-text">
                Den Spiel- oder Kategorienamen anstelle des Streamtitels als Kapiteltitel verwenden.
              </div>
            </div>

            <!-- Codec Preferences (H.265/AV1 Support - Streamlink 8.0.0+) -->
            <div class="section-header" style="margin-top: 2rem;">
              <svg class="section-icon">
                <use href="#icon-settings" />
              </svg>
              <h3 class="section-title">Video-Codecs</h3>
            </div>
            <div class="form-group">
              <label>Erlaubte Codecs:</label>
              <select v-model="data.supported_codecs" class="form-control">
                <option value="h264">Nur H.264 - bis 1080p60, höchste Kompatibilität</option>
                <option value="h265">Nur H.265/HEVC - 1440p60, moderne Hardware erforderlich</option>
                <option value="av1">Nur AV1 - experimentell, aktuelle Hardware erforderlich</option>
                <option value="h264,h265">H.264 + H.265 (empfohlen) - automatischer Rückfall</option>
                <option value="h264,h265,av1">Alle Codecs - maximale Qualität</option>
              </select>
              <div class="help-text">
                Codec-Unterstützung für hochauflösende Aufnahmen bis 1440p60 einstellen.
                <br><br><strong>Hinweise:</strong>
                <ul style="margin-top: 0.5rem; margin-bottom: 0;">
                  <li>Die verfügbaren Codecs hängen von den <strong>Einstellungen des Senders</strong> ab.</li>
                  <li>Die meisten Kanäle senden nur in H.264.</li>
                  <li>H.265 und AV1 benötigen moderne Hardware und kompatible Player.</li>
                  <li>Ist der gewählte Codec nicht verfügbar, verwendet Streamlink automatisch einen verfügbaren Codec.</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- Storage section -->
        <div v-if="section === 'storage'" class="tab-panel">
          <div class="panel-block">
            <div class="section-header">
              <svg class="section-icon">
                <use href="#icon-server" />
              </svg>
              <h3 class="section-title">Speicher und Aufbewahrung</h3>
            </div>
            <p class="section-description">
              Automatische Bereinigung und Schutzregeln für alle Kanäle festlegen. Einzelne Kanäle können diese Vorgabe erben oder eigene Regeln verwenden.
            </p>

            <CleanupPolicyEditor
              :is-global="true"
              title="Globale Aufbewahrung"
              @saved="handleCleanupPolicySaved"
            />
          </div>
        </div>
      </div>

      <!-- Save Button (recording settings only; cleanup policies save themselves) -->
      <div v-if="context === 'global' && section === 'recording'" class="form-actions">
        <button @click="saveSettings" class="btn btn-primary" :disabled="isSaving">
          {{ isSaving ? 'Wird gespeichert...' : 'Einstellungen speichern' }}        </button>
      </div>

    <!-- Active Recordings -->
    <div v-if="context !== 'global' && activeRecordings.length > 0" class="active-recordings panel-block">
      <h3>Laufende Aufnahmen</h3>
      <div class="recordings-grid">
        <div v-for="recording in activeRecordings" :key="recording.streamer_id" class="recording-card">
          <div class="recording-header">
            <span class="streamer-name">{{ recording.streamer_name }}</span>
            <span class="recording-indicator">AUFNAHME LÄUFT</span>
          </div>
          <div class="recording-details">
            <div><strong>Gestartet:</strong> {{ formatDate(recording.started_at) }}</div>
            <div><strong>Dauer:</strong> {{ formatDuration(recording.duration) }}</div>
            <div><strong>Status:</strong> {{ recording.status }}</div>
            <div><strong>Twitch-Zugang:</strong> {{ recording.effective_auth_mode || 'unknown' }}</div>
            <div v-if="recordingStatus(recording).handoff" class="warning-message">
              {{ recordingStatus(recording).handoff }}
            </div>
            <div v-if="recordingStatus(recording).partialWarning" class="warning-message">
              {{ recordingStatus(recording).partialWarning }}
            </div>
            <div class="output-path"><strong>Datei:</strong> {{ recording.file_path || recording.output_path }}</div>
          </div>
          <button @click="stopRecording(recording.streamer_id)" class="btn btn-danger" :disabled="isLoading">
            Aufnahme stoppen
          </button>
        </div>
      </div>
    </div>
    <!-- Streamer Settings -->
    <div v-if="context !== 'global'" class="streamer-settings panel-block">
      <h3>{{ context === 'manage' ? 'Aufnahmen für alle Kanäle' : 'Aufnahme für diesen Kanal' }}</h3>

      <div v-if="!streamerSettings || streamerSettings.length === 0" class="no-streamers-message">
        <p>Keine Kanäle vorhanden. Füge zuerst einen Kanal hinzu.</p>
      </div>
        <template v-else>
        <div v-if="context === 'manage'" class="table-controls">
          <button @click="toggleAllStreamers(true)" class="btn btn-secondary">Aufnahme für alle aktivieren</button>
          <button @click="toggleAllStreamers(false)" class="btn btn-secondary">Aufnahme für alle deaktivieren</button>
        </div>

        <div v-if="context === 'channel'" class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Kanal</th>
                <th v-if="showOverrides">
                  <span class="th-content">
                    Aufnehmen
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Aufnahme für diesen Kanal aktivieren oder deaktivieren</span>
                      </span>
                    </span>
                  </span>
                </th>
                <th v-if="showOverrides">
                  <span class="th-content">
                    Qualität
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Aufnahmequalität wählen oder die globale Vorgabe verwenden</span>
                      </span>
                    </span>
                  </span>
                </th>
                <!-- Dormant Twitch-auth priority control retained for a future
                     product decision; intentionally not rendered:
                <th>Auth priority</th>
                -->
                <th v-if="showOverrides">
                  <span class="th-content">
                    Eigener Dateiname
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Optionale eigene Dateinamenvorlage für diesen Kanal</span>
                      </span>
                    </span>
                  </span>
                </th>
                <th>
                  <span class="th-content">
                    Aktionen
                    <span class="th-tooltip-wrapper">
                      <svg class="info-icon">
                        <use href="#icon-info" />
                      </svg>
                      <span class="tooltip-wrapper">
                        <span class="tooltip">Aufnahme stoppen und Aufbewahrung bearbeiten</span>
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
                  <span class="streamer-name">{{ streamer.username || 'Unbekannter Kanal' }}</span>
                </td>
                <td v-if="showOverrides" data-label="Aufnehmen">
                  <input type="checkbox" v-model="streamer.enabled"
                    :aria-label="`Aufnahme für ${streamer.username || 'Kanal'}`"
                    @change="updateStreamerSetting(streamer.streamer_id, { enabled: streamer.enabled })" />
                </td>
                <td v-if="showOverrides" data-label="Qualität">
                  <select v-model="streamer.quality"
                    @change="updateStreamerSetting(streamer.streamer_id, { quality: streamer.quality })"
                    class="form-control form-control-sm">
                    <option value="">Globale Vorgabe verwenden</option>
                    <option v-for="option in QUALITY_OPTIONS" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </td>
                <!-- Former compatibility-only editor (intentionally inactive):
                <td data-label="Auth priority">
                  <input type="number" :value="streamer.twitch_auth_priority ?? 0"
                    min="-1000" max="1000" step="1"
                    @change="updateTwitchAuthPriority(streamer, $event)" />
                </td>
                -->
                <td v-if="showOverrides" data-label="Eigener Dateiname">
                  <input type="text" v-model="streamer.custom_filename"
                    @change="updateStreamerSetting(streamer.streamer_id, { custom_filename: streamer.custom_filename })"
                    placeholder="Globale Vorlage verwenden" class="form-control form-control-sm" />
                </td>
                <td data-label="Aktionen" class="actions-cell">
                  <div class="actions-group">
                    <button
                      v-if="isActiveRecording(streamer.streamer_id)"
                      @click="stopRecording(streamer.streamer_id)"
                      class="btn btn-danger btn-sm"
                      :disabled="isLoading">
                      Stoppen
                    </button>
                    <button
                      @click="openCleanupPolicyEditor(streamer)"
                      class="btn btn-secondary btn-sm"
                      :disabled="isLoading"
                      title="Aufbewahrung für diesen Kanal konfigurieren">
                      Aufbewahrung
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
    <BaseModal
      v-model="showStreamerPolicyDialog"
      :title="`Cleanup Policy for ${selectedStreamer?.username || 'Streamer'}`"
      size="lg"
    >
      <CleanupPolicyEditor
        v-if="selectedStreamer"
        :streamer-id="selectedStreamer.streamer_id"
        :title="`Cleanup Policy for ${selectedStreamer.username}`"
        :is-global="false"
        @saved="handleStreamerPolicySaved"
      />
    </BaseModal>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { useFilenamePresets } from '@/composables/useFilenamePresets';
import { useToast } from '@/composables/useToast';
import { toRecordingStatusSummary } from '@/services/recording-status';
import { QUALITY_OPTIONS, FILENAME_VARIABLES } from '@/types/recording';
import type { ActiveRecording, RecordingSettings, StreamerRecordingSettings } from '@/types/recording';
import CleanupPolicyEditor from '@/components/CleanupPolicyEditor.vue';
import BaseModal from '@/components/base/BaseModal.vue';

const props = withDefaults(defineProps<{
  settings: RecordingSettings | null;
  streamerSettings: StreamerRecordingSettings[];
  activeRecordings: ActiveRecording[];
  /** Which settings page this instance renders: recording quality/behavior
   *  or the storage/cleanup half. Each is its own sidebar section now -
   *  the old in-panel tab bar is gone. */
  section?: 'recording' | 'storage';
  context?: 'global' | 'channel' | 'manage';
  showOverrides?: boolean;
}>(), {
  section: 'recording',
  context: 'global',
  showOverrides: true
});

const emits = defineEmits<{
  update: [settings: RecordingSettings];
  updateStreamer: [streamerId: number, settings: Partial<StreamerRecordingSettings>];
  stopRecording: [streamerId: number];
}>();

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

/* Dormant UI mutation path retained while Twitch-auth priority is disabled:
const updateTwitchAuthPriority = (
  streamer: StreamerRecordingSettings,
  event: Event
) => {
  const input = event.target as HTMLInputElement;
  const rawPriority = input.value.trim();
  const priority = Number(rawPriority);
  if (!rawPriority || !Number.isInteger(priority) || priority < -1000 || priority > 1000) {
    input.value = String(streamer.twitch_auth_priority ?? 0);
    return;
  }
  updateStreamerSetting(streamer.streamer_id, { twitch_auth_priority: priority });
};
*/
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
  return props.activeRecordings.some((rec) => rec.streamer_id === streamerId);
};

const recordingStatus = (recording: ActiveRecording) => (
  toRecordingStatusSummary(recording)
);

const formatDate = (date: string) => {
  return new Date(date).toLocaleString();
};

const formatDuration = (seconds: number) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
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

const handleStreamerPolicySaved = (_policy: any) => {

  closeStreamerPolicyDialog();
};
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;


// Match the shared .settings-group look so recording blocks read as the
// same "these belong together" containers as every other settings page
.panel-block {
  padding: var(--spacing-5);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: rgba(var(--background-darker-rgb, 10, 10, 10), 0.35);
  margin-bottom: var(--spacing-5);

  &:last-child {
    margin-bottom: 0;
  }
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

/* (Tab bar removed - Recording and Storage are separate settings sections) */
.tab-panel {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Mobile-First-Ansatz - Basis-Styles für mobile Geräte */

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
  background-color: var(--background-dark);
  color: var(--text-primary);
  border-radius: var(--border-radius);
  box-sizing: border-box;
}

/* Error state for form controls */
.form-control.error {
  border-color: var(--danger-color);
  background-color: rgba(239, 68, 68, 0.1);
}


.checkbox-target {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 44px;
  cursor: pointer;
}

.data-table td > input[type="checkbox"] {
  width: 44px;
  height: 44px;
  cursor: pointer;
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
// VARIABLE TAGS (Filename template variables)
// ============================================================================

.variables-container {
  display: flex;
  flex-wrap: wrap;
  gap: v.$spacing-2;  // 8px gap between tags
  margin-top: v.$spacing-3;  // 12px top margin
  margin-bottom: v.$spacing-2;  // 8px bottom margin
}

.variable-tag {
  display: inline-flex;
  align-items: center;
  background: var(--background-darker);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: v.$spacing-2 v.$spacing-3;  // 8px 12px
  font-family: var(--font-mono);
  font-size: v.$text-sm;
  font-weight: v.$font-medium;
  white-space: nowrap;
  transition: v.$transition-all;

  &.clickable {
    cursor: pointer;

    &:hover {
      background: var(--primary-color);
      color: white;
      border-color: var(--primary-color);
      transform: translateY(-1px);
    }

    &:active {
      transform: translateY(0);
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
