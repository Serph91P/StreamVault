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
  // SECURITY: Only enable if URL is configured - prevents errors when no URL is set
  notificationsEnabled: props.settings.notifications_enabled === true && !!props.settings.notification_url,
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
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// ============================================================================
// NOTIFICATION SETTINGS PANEL - Unified Design
// Most styles inherited from global _settings-panels.scss
// ============================================================================

// ============================================================================
// NOTIFICATION TYPE CARDS
// ============================================================================

.notification-types {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: v.$spacing-4;
  margin-bottom: v.$spacing-6;
  
  @include m.respond-below('sm') {
    grid-template-columns: 1fr;
  }
}

.notification-type-card {
  padding: v.$spacing-4;
  background: var(--background-card);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: v.$transition-all;
  cursor: pointer;
  
  &:hover {
    border-color: var(--primary-color);
    background: var(--background-hover);
  }
  
  &.active {
    border-color: var(--primary-color);
    background: var(--primary-bg);
  }
  
  .type-icon {
    font-size: v.$text-2xl;
    margin-bottom: v.$spacing-2;
  }
  
  .type-title {
    font-weight: v.$font-semibold;
    color: var(--text-primary);
    margin-bottom: v.$spacing-1;
  }
  
  .type-description {
    font-size: v.$text-sm;
    color: var(--text-secondary);
  }
}

// ============================================================================
// TEST NOTIFICATION BUTTON
// ============================================================================

.test-notification-section {
  margin-top: v.$spacing-6;
  padding: v.$spacing-4;
  background: var(--info-bg-color);
  border: 1px solid var(--info-border-color);
  border-radius: var(--radius-md);
  
  .test-result {
    margin-top: v.$spacing-3;
    padding: v.$spacing-3;
    border-radius: var(--radius-sm);
    
    &.success {
      background: var(--success-bg-color);
      border: 1px solid var(--success-border-color);
      color: var(--success-color);
    }
    
    &.error {
      background: var(--danger-bg-color);
      border: 1px solid var(--danger-border-color);
      color: var(--danger-color);
    }
  }
}

// ============================================================================
// CHECKBOX GROUP - Better spacing
// ============================================================================

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-4;  // More spacing between checkboxes
  
  label {
    display: flex;
    align-items: flex-start;
    gap: v.$spacing-3;
    padding: v.$spacing-3;
    background: var(--background-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    transition: v.$transition-all;
    cursor: pointer;
    
    &:hover {
      border-color: var(--primary-color);
      background: var(--background-hover);
    }
    
    input[type="checkbox"] {
      margin-top: 2px;  // Align with text
      flex-shrink: 0;
    }
  }
  
  @include m.respond-below('md') {
    gap: v.$spacing-3;
    
    label {
      padding: v.$spacing-4;
      min-height: 44px;  // Touch-friendly
    }
  }
}

// ============================================================================
// FORM ACTIONS - Better button alignment
// ============================================================================

.form-actions {
  display: flex;
  gap: v.$spacing-3;
  flex-wrap: wrap;
  
  .btn {
    flex: 1;
    min-width: 150px;
    
    &:last-child {
      margin-left: 0 !important;  // Remove inline margin
    }
  }
}

// ============================================================================
// STREAMER NOTIFICATIONS TABLE - Better spacing
// ============================================================================

.streamer-notifications {
  margin-top: v.$spacing-6;
  
  h3 {
    margin-bottom: v.$spacing-4;
  }
  
  .table-wrapper {
    margin-top: v.$spacing-4;  // Space from table controls
  }
}

// ============================================================================
// RESPONSIVE
// ============================================================================

@include m.respond-below('md') {
  .form-actions {
    flex-direction: column;
    gap: v.$spacing-3;
    
    .btn {
      width: 100%;
      min-width: 100%;
      flex: none;
    }
  }
  
  .streamer-notifications {
    h3 {
      font-size: v.$text-xl;
    }
  }
}
</style>
