<template>
  <div>
    <h3>Notification Settings</h3>
    
    <!-- Global Settings -->
    <div class="settings-form">
      <div class="form-group">
        <label>Notification Service URL:</label>
        <div class="input-with-tooltip">
          <input 
            v-model="data.notificationUrl" 
            placeholder="e.g., discord://webhook1,telegram://bot_token/chat_id"
            class="form-control"
            :class="{ 'is-invalid': showValidationError && !isValidNotificationUrl && data.notificationUrl.trim() }"
            @focus="showTooltip = true"
            @input="handleInput"
            @blur="handleBlur"
          />
          <div 
            v-if="showValidationError && !isValidNotificationUrl && data.notificationUrl.trim()" 
            class="invalid-feedback"
          >
            Please enter a valid URL (e.g., discord://webhook_id/webhook_token)
          </div>
          <div 
            v-if="showTooltip" 
            class="tooltip-wrapper"
            @mouseenter="handleTooltipMouseEnter"
            @mouseleave="handleTooltipMouseLeave"
          >
            <div class="tooltip">
              StreamVault supports over 100 notification services including Discord, Telegram, Ntfy, 
              Pushover, Slack and more. Check the 
              <a 
                href="https://github.com/caronc/apprise/wiki#notification-services"
                target="_blank" 
                rel="noopener noreferrer"
                @click.stop
                class="tooltip-link"
              >Apprise Documentation</a> for supported services and URL formats.
            </div>
          </div>
        </div>
      </div>
      
      <div class="form-group">
        <label>
          <input type="checkbox" v-model="data.notificationsEnabled" />
          Enable Notifications
        </label>
      </div>
      
      <div class="form-group">
        <h4>Global Notification Settings</h4>
        <div class="checkbox-group">
          <!-- Checkboxes... -->
        </div>
      </div>
      
      <!-- System Notification Settings (NEW) -->
      <div class="form-group">
        <h4>System Notification Settings</h4>
        <p class="section-description">
          Configure which recording events trigger external notifications (Discord, Telegram, etc.)
        </p>
        <div class="checkbox-group">
          <label>
            <input type="checkbox" v-model="data.notifyRecordingStarted" />
            Recording Started
            <span class="label-hint">(may be noisy - every stream triggers recording)</span>
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyRecordingFailed" />
            Recording Failed ⚠️
            <span class="label-hint label-recommended">(RECOMMENDED - know when recordings fail)</span>
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyRecordingCompleted" />
            Recording Completed
            <span class="label-hint">(may be noisy - most recordings complete normally)</span>
          </label>
        </div>
      </div>

      <div class="form-actions">
        <button 
          @click="saveSettings" 
          class="btn btn-primary"
          :disabled="isSaving || !canSave"
        >
          {{ isSaving ? 'Saving...' : 'Save Settings' }}
        </button>
        <button 
          @click="testNotification" 
          class="btn btn-secondary"
          :disabled="!data.notificationsEnabled || !data.notificationUrl"
        >
          Test Notification
        </button>
        <button 
          @click="testWebSocketNotification" 
          class="btn btn-secondary"
          style="margin-left: 10px;"
        >
          Test WebSocket
        </button>
      </div>
    </div>

    <!-- Streamer Notification Table -->
    <div class="streamer-notifications">
      <h3>Streamer Notifications</h3>
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
                Online
                <div class="th-tooltip">Notify when stream starts</div>
              </th>
              <th>
                Offline
                <div class="th-tooltip">Notify when stream ends</div>
              </th>
              <th>
                Updates
                <div class="th-tooltip">Notify on title/category changes</div>
              </th>
              <th>
                Favorites
                <div class="th-tooltip">Notify when streaming favorite games</div>
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="streamer in typedStreamerSettings" :key="streamer.streamer_id">
              <td class="streamer-info">
                <div class="streamer-avatar" v-if="streamer.profile_image_url">
                  <img 
                    :src="streamer.profile_image_url" 
                    :alt="streamer.username || ''"
                  />
                </div>
                <span class="streamer-name">{{ streamer.username || 'Unknown Streamer' }}</span>
              </td>              <td data-label="Online">
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_online"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_online: streamer.notify_online })"
                />
              </td>
              <td data-label="Offline">
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_offline"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_offline: streamer.notify_offline })"
                />
              </td>
              <td data-label="Updates">
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_update"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_update: streamer.notify_update })"
                />
              </td>
              <td data-label="Favorites">
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_favorite_category"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_favorite_category: streamer.notify_favorite_category })"
                />
              </td>              <td class="actions-cell">
                <div class="btn-group">
                  <button 
                    @click="toggleAllForStreamer(streamer.streamer_id, true)" 
                    class="btn btn-sm btn-secondary"
                  >On</button>
                  <button 
                    @click="toggleAllForStreamer(streamer.streamer_id, false)" 
                    class="btn btn-sm btn-secondary"
                  >Off</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useToast } from '@/composables/useToast'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

// Props
const props = defineProps({
  settings: {
    type: Object as () => NotificationSettings,
    required: true
  },
  streamerSettings: {
    type: Array as () => StreamerNotificationSettings[],
    required: true
  }
})

// Typed version of streamerSettings to fix TS errors
const typedStreamerSettings = computed(() => {
  return props.streamerSettings as StreamerNotificationSettings[]
})

// Emits
const emit = defineEmits(['update-settings', 'update-streamer-settings', 'test-notification'])
const toast = useToast()

// Data kopieren, um sie im Formular zu verwenden
const data = ref({
  notificationUrl: props.settings.notification_url || '',
  notificationsEnabled: props.settings.notifications_enabled !== false,
  notifyOnlineGlobal: props.settings.notify_online_global !== false,
  notifyOfflineGlobal: props.settings.notify_offline_global !== false, 
  notifyUpdateGlobal: props.settings.notify_update_global !== false,
  notifyFavoriteCategoryGlobal: props.settings.notify_favorite_category_global !== false,
  // System notification settings (NEW - Migration 028)
  notifyRecordingStarted: props.settings.notify_recording_started !== undefined ? props.settings.notify_recording_started : false,
  notifyRecordingFailed: props.settings.notify_recording_failed !== undefined ? props.settings.notify_recording_failed : true,
  notifyRecordingCompleted: props.settings.notify_recording_completed !== undefined ? props.settings.notify_recording_completed : false
})

// Add these new refs for validation
const showValidationError = ref(false)
const inputTimeout = ref<number | null>(null)
const showTooltip = ref(false)
let tooltipTimeout: number | undefined = undefined

// Handle input with debounce
const handleInput = () => {
  // Clear existing timeout
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value)
  }
  
  // Set a new timeout to show validation after typing stops
  inputTimeout.value = window.setTimeout(() => {
    showValidationError.value = true
  }, 1000) // Show validation error 1 second after typing stops
}

// Handle blur event (when user clicks outside the input)
const handleBlur = () => {
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value)
  }
  showValidationError.value = true
}

const handleTooltipMouseEnter = () => {
  if (tooltipTimeout) {
    window.clearTimeout(tooltipTimeout)
    tooltipTimeout = undefined
  }
  showTooltip.value = true
}

const handleTooltipMouseLeave = () => {
  tooltipTimeout = window.setTimeout(() => {
    showTooltip.value = false
  }, 300)
}

// Cleanup timeout on component unmount
onUnmounted(() => {
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value)
  }
  if (tooltipTimeout) {
    window.clearTimeout(tooltipTimeout)
  }
})

// Validierung und Speichern
const KNOWN_SCHEMES = [
  'discord', 'telegram', 'tgram', 'slack', 'pushover', 'mailto',
  'ntfy', 'matrix', 'twilio', 'msteams', 'slack', 'gchat', 'ligne',
  'signal', 'whatsapp', 'rocket', 'pushbullet', 'apprise', 'http',
  'https', 'twitter', 'slack', 'dbus'
]

const isSaving = ref(false)

const isValidNotificationUrl = computed(() => {
  const url = data.value.notificationUrl.trim()
  
  // Empty URL is considered valid (though not for saving)
  if (!url) return true
  
  // Handle multiple URLs separated by comma
  if (url.includes(',')) {
    return url.split(',')
      .every((part: string) => {
        const trimmedPart = part.trim()
        return trimmedPart === '' || validateSingleUrl(trimmedPart)
      })
  }
  
  return validateSingleUrl(url)
})

const validateSingleUrl = (url: string): boolean => {
  // Basic URL structure check
  if (!url.includes('://')) return false
  
  // Extract scheme
  const scheme = url.split('://')[0].toLowerCase()
  
  // Check against known schemes
  if (KNOWN_SCHEMES.includes(scheme)) return true
  
  // Allow custom schemes that follow the pattern: xxx://
  return /^[a-zA-Z]+:\/\/.+/.test(url)
}

// Can Save Computed
const canSave = computed(() => {
  return isValidNotificationUrl.value && 
         (data.value.notificationUrl.trim() !== '' || !data.value.notificationsEnabled)
})

// Aktionen
const saveSettings = async () => {
  if (isSaving.value) return
  
  try {
    isSaving.value = true
    emit('update-settings', {
      notification_url: data.value.notificationUrl,
      notifications_enabled: data.value.notificationsEnabled,
      notify_online_global: data.value.notifyOnlineGlobal,
      notify_offline_global: data.value.notifyOfflineGlobal,
      notify_update_global: data.value.notifyUpdateGlobal,
      notify_favorite_category_global: data.value.notifyFavoriteCategoryGlobal,
      // System notification settings (Migration 028)
      notify_recording_started: data.value.notifyRecordingStarted,
      notify_recording_failed: data.value.notifyRecordingFailed,
      notify_recording_completed: data.value.notifyRecordingCompleted
    })
  } catch (error) {
    console.error('Failed to save settings:', error)
  } finally {
    isSaving.value = false
  }
}

const updateStreamerSettings = (streamerId: number, settings: Partial<StreamerNotificationSettings>) => {
  emit('update-streamer-settings', streamerId, settings)
}

const toggleAllForStreamer = (streamerId: number, enabled: boolean) => {
  if (!streamerId) return
  
  const settingsUpdate: Partial<StreamerNotificationSettings> = {
    notify_online: enabled,
    notify_offline: enabled,
    notify_update: enabled
  }

  emit('update-streamer-settings', streamerId, settingsUpdate)
}

const toggleAllStreamers = (enabled: boolean) => {
  if (!props.streamerSettings) return
  
  for (const streamer of typedStreamerSettings.value) {
    if (!streamer?.streamer_id) continue
    
    toggleAllForStreamer(streamer.streamer_id, enabled)
  }
}

const testNotification = () => {
  emit('test-notification')
}

const testWebSocketNotification = async () => {
  try {
    const response = await fetch('/api/settings/test-websocket-notification', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to send test WebSocket notification')
    }

    toast.success('Test WebSocket notification sent! Check the notification bell.')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to send test WebSocket notification')
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.settings-form {
  margin-bottom: 30px;
  background-color: var(--background-darker, #1f1f23);
  padding: var(--spacing-6);
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

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm, 8px);
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

.section-description {
  color: var(--text-secondary, #adadb8);
  font-size: 0.875rem;
  margin-bottom: var(--spacing-md, 12px);
  line-height: 1.5;
}

.label-hint {
  color: var(--text-secondary, #adadb8);
  font-size: 0.8rem;
  font-style: italic;
  margin-left: var(--spacing-xs, 4px);
}

.label-recommended {
  color: var(--warning-color, #f59e0b);
  font-weight: 500;
}

.input-with-tooltip {
  position: relative;
}

.form-control {
  width: 100%;
  padding: var(--spacing-3);
  border: 1px solid var(--border-color, #333);
  background-color: var(--background-dark, #18181b);
  color: var(--text-primary, #fff);
  border-radius: var(--border-radius, 4px);
}

.form-control.is-invalid {
  border-color: var(--danger-color, #ef4444);
}

.invalid-feedback {
  color: var(--danger-color, #ef4444);
  font-size: 0.875rem;
  margin-top: var(--spacing-xs, 4px);
}

.tooltip-wrapper {
  position: absolute;
  top: 100%;
  left: 0;
  width: 100%;
  z-index: 1000;
  margin-top: var(--spacing-sm, 8px);
}

.tooltip {
  background-color: var(--background-dark, #18181b);
  color: var(--text-secondary, #adadb8);
  padding: var(--spacing-md, 12px);
  border-radius: var(--border-radius, 4px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  font-size: 0.875rem;
  line-height: 1.5;
}

.tooltip-link {
  color: var(--primary-color, #42b883);
  text-decoration: underline;
}

.form-actions {
  display: flex;
  gap: var(--spacing-sm, 10px);
  margin-top: var(--spacing-lg, 20px);
}

.btn {
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: var(--border-radius, 6px);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn-primary {
  background-color: var(--primary-color, #42b883);
  color: white;  /* White text is correct on primary-color background */
}

.btn-secondary {
  background-color: var(--background-card, #3a3a3a);
  color: var(--text-primary);  /* Theme-aware text color */
  border: 1px solid var(--border-color);
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

.btn-sm {
  padding: var(--spacing-1) var(--spacing-2);
  font-size: 0.875rem;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: auto;
}

.streamer-notifications {
  margin-top: var(--spacing-xl, 30px);
}

.table-controls {
  display: flex;
  gap: var(--spacing-sm, 10px);
  margin-bottom: var(--spacing-md, 15px);
}

.streamer-table {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin-bottom: var(--spacing-lg, 20px);
}

.streamer-table table {
  width: 100%;
  min-width: 600px;
  border-collapse: collapse;
  background-color: var(--background-darker, #1f1f23);
  border-radius: var(--border-radius, 8px);
  border: 1px solid var(--border-color, #303034);
  overflow: hidden;
}

/* Fix table striping */
.streamer-table table tr {
  background-color: transparent;
}

.streamer-table table tr:nth-child(even) {
  background-color: rgba(0, 0, 0, 0.15);
}

.streamer-table th {
  background-color: rgba(0, 0, 0, 0.2);
  font-weight: 500;
  color: var(--text-secondary, #ccc);
  position: relative;
  padding: var(--spacing-3) var(--spacing-4);
  text-align: left;
  border-bottom: 1px solid var(--border-color, #333);
}

.streamer-table td {
  padding: var(--spacing-3) var(--spacing-4);
  text-align: left;
  border-bottom: 1px solid var(--border-color, #333);
}

.streamer-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 10px);
  min-height: 44px; /* Consistent cell height for touch targets */
}

.streamer-name {
  line-height: 1.4;
  /* Removed inline-block, vertical-align - flex handles alignment */
}

.streamer-avatar {
  width: 32px;
  height: 32px;
  min-width: 32px; /* Prevent shrinking - consistent with RecordingSettingsPanel */
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
}

.streamer-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.streamer-table tr:last-child td {
  border-bottom: none;
}

.th-tooltip {
  font-size: 0.8rem;
  font-weight: normal;
  color: var(--text-secondary, #aaa);
  margin-top: var(--spacing-xs, 4px);
}

.btn-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.actions-cell {
  white-space: nowrap;
}

@include m.respond-below('md') {  // < 768px
  .streamer-table {
    border-radius: 0;
  }
  
  .btn {
    padding: var(--spacing-2) var(--spacing-3);
    font-size: 0.9rem;
  }
  
  .btn-sm {
    padding: var(--spacing-1) var(--spacing-2);
    font-size: 0.8rem;
  }
  
  .table-controls {
    flex-direction: column;
    align-items: stretch;
  }
  
  .table-controls button {
    margin-right: 0;
  }
  
  /* Fix alignment in table cells */
  .streamer-table td, .streamer-table th {
    padding: var(--spacing-2) var(--spacing-2);
  }
  
  /* Fix the streamer info height */
  .streamer-info {
    gap: 6px;
  }
  
  .streamer-name {
    font-size: 0.9rem;
  }
  
  /* Make checkboxes easier to tap on mobile */
  input[type="checkbox"] {
    min-width: 20px;  /* Increased from 18px for better touch targets */
    min-height: 20px;
    cursor: pointer;
  }
}

/* Mobile Card Layout: Transform table to cards on mobile (< 768px) */
@include m.respond-below('md') {  // < 767px
  .streamer-table table,
  .streamer-table thead,
  .streamer-table tbody,
  .streamer-table th,
  .streamer-table td,
  .streamer-table tr {
    display: block;
  }
  
  /* Hide table header */
  .streamer-table thead tr {
    position: absolute;
    top: -9999px;
    left: -9999px;
  }
  
  /* Style each row as a card */
  .streamer-table tr {
    margin-bottom: var(--spacing-4, 16px);
    border-radius: var(--border-radius, 8px);
    border: 1px solid var(--border-color, #333);
    background: var(--background-card, #2a2a2e);
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }
  
  /* Style table cells as rows */
  .streamer-table td {
    position: relative;
    padding: 12px 12px 12px 120px; /* Space for labels */
    min-height: 44px;  /* Touch-friendly height */
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--border-color-subtle, rgba(255, 255, 255, 0.05));
  }
  
  .streamer-table td:last-child {
    border-bottom: none;
  }
  
  /* Add labels before each cell */
  .streamer-table td:before {
    content: attr(data-label);
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    left: 12px;
    width: 95px;
    padding-right: 10px;
    font-weight: 600;
    white-space: nowrap;
    color: var(--text-secondary, #adadb8);
    font-size: 0.85rem;
  }
  
  /* Streamer info cell (first cell) */
  .streamer-table td.streamer-info {
    padding: var(--spacing-3);
    font-weight: 600;
    background: var(--background-darker, #1f1f23);
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .streamer-table td.streamer-info:before {
    display: none;  /* No label for streamer name */
  }
  
  /* Actions cell */
  .streamer-table td.actions-cell {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    padding-left: 12px;
  }
  
  .streamer-table td.actions-cell:before {
    content: '';  /* Empty label for actions */
  }
  
  .btn-group {
    margin-left: auto;
  }
  
  /* Make buttons full width on mobile for easier tapping */
  .streamer-table .btn-sm {
    padding: var(--spacing-2) var(--spacing-4);
    min-width: 60px;
    font-size: 0.875rem;
  }
}

/* Extra small screens: Additional optimizations */
@include m.respond-below('xs') {  // < 480px
  .streamer-table tr {
    margin-bottom: var(--spacing-3, 12px);
  }
  
  .streamer-table td {
    padding-left: 100px;  /* Slightly less padding */
  }
  
  .streamer-table td:before {
    width: 85px;
    font-size: 0.8rem;
  }
}
</style>
