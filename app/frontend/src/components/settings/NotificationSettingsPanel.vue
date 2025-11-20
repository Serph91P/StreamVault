<template>
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

    <!-- Streamer Notification Table -->
    <div class="streamer-notifications">
      <h3>Streamer Notifications</h3>
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
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { UI } from '@/config/constants'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'
import GlassCard from '@/components/cards/GlassCard.vue'

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
  }, UI.VALIDATION_DEBOUNCE_MS)
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
  }, UI.SEARCH_DEBOUNCE_MS)
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

.settings-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-7, 28px);
}

.settings-form,
.streamer-notifications {
  margin-bottom: 0;
  background: transparent;
  padding: 0;
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

.streamer-notifications {
  margin-top: var(--spacing-xl, 30px);
}

.table-controls {
  display: flex;
  gap: var(--spacing-sm, 10px);
  margin-bottom: var(--spacing-md, 15px);
}

/* Avatar placeholder for missing images */
.avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-color);
  color: white;
  font-weight: bold;
  font-size: 14px;
}

@include m.respond-below('md') {  // < 768px
  /* Form Controls - iOS Zoom Prevention & Touch Targets */
  .form-control {
    padding: 12px;
    font-size: 16px !important; /* Prevent iOS zoom */
    min-height: 48px;
    border-radius: var(--border-radius, 8px);
  }
  
  input[type="text"],
  input[type="email"],
  input[type="url"],
  textarea {
    font-size: 16px !important; /* Prevent iOS zoom */
    min-height: 48px;
  }
  
  /* Form Actions - Stack Vertically on Mobile */
  .form-actions {
    flex-direction: column;
    gap: 12px;
  }
  
  .form-actions .btn {
    width: 100%;
    min-height: 48px; /* Touch-friendly */
    font-size: 16px;
    padding: 12px 16px;
  }
  
  /* Checkbox groups - Better touch targets */
  .checkbox-group input[type="checkbox"] {
    width: 20px;
    height: 20px;
    margin-right: 12px;
  }
  
  .checkbox-group label {
    padding: 8px 0;
    min-height: 44px;
    display: flex;
    align-items: center;
  }
  
  /* Table Controls - Stack Vertically */
  .table-controls {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  
  .table-controls button {
    margin-right: 0;
    width: 100%;
    min-height: 48px;
    font-size: 16px;
  }
  
  .streamer-table {
    border-radius: 0;
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
  
  /* Table Controls - Stack Vertically on Mobile */
  .table-controls {
    flex-direction: column;
    gap: 12px;
  }
  
  .table-controls button {
    width: 100%;
    min-height: 48px;
    font-size: 16px;
  }
}
</style>
