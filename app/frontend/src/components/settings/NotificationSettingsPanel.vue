<template>
  <div>
    <h3>Benachrichtigungseinstellungen</h3>
    
    <!-- Global Settings -->
    <div class="settings-form">
      <div class="form-group">
        <label>Notification Service URL:</label>
        <div class="input-with-tooltip">
          <input 
            v-model="data.notificationUrl" 
            placeholder="z.B. discord://webhook1,telegram://bot_token/chat_id"
            class="form-control"
            :class="{ 'is-invalid': !isValidNotificationUrl && data.notificationUrl.trim() }"
            @focus="showTooltip = true"
          />
          <div 
            v-if="!isValidNotificationUrl && data.notificationUrl.trim()" 
            class="invalid-feedback"
          >
            Bitte gib eine gültige URL ein (z.B. discord://webhook_id/webhook_token)
          </div>
          <div 
            v-if="showTooltip" 
            class="tooltip-wrapper"
            @mouseenter="handleTooltipMouseEnter"
            @mouseleave="handleTooltipMouseLeave"
          >
            <Tooltip>
              StreamVault unterstützt 100+ Benachrichtigungsdienste wie Discord, Telegram, Ntfy, 
              Pushover, Slack und mehr. Schau in der 
              <a 
                href="https://github.com/caronc/apprise/wiki#notification-services"
                target="_blank" 
                rel="noopener noreferrer"
                @click.stop
                class="tooltip-link"
              >Apprise-Dokumentation</a> nach unterstützten Diensten und URL-Formaten.
            </Tooltip>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label>
          <input type="checkbox" v-model="data.notificationsEnabled" />
          Benachrichtigungen aktivieren
        </label>
      </div>
      
      <div class="form-group">
        <h4>Globale Benachrichtigungseinstellungen</h4>
        <div class="checkbox-group">
          <label>
            <input type="checkbox" v-model="data.notifyOnlineGlobal" />
            Stream-Start Benachrichtigungen
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyOfflineGlobal" />
            Stream-Ende Benachrichtigungen
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyUpdateGlobal" />
            Stream-Update Benachrichtigungen
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyFavoriteCategoryGlobal" />
            Benachrichtigungen für Favoriten-Spiele
          </label>
        </div>
      </div>

      <div class="form-actions">
        <button 
          @click="saveSettings" 
          class="btn btn-primary"
          :disabled="isSaving || !canSave"
        >
          {{ isSaving ? 'Speichern...' : 'Einstellungen speichern' }}
        </button>
        <button 
          @click="testNotification" 
          class="btn btn-secondary"
          :disabled="!data.notificationsEnabled || !data.notificationUrl"
        >
          Test-Benachrichtigung
        </button>
      </div>
    </div>

    <!-- Streamer Notification Table -->
    <div class="streamer-notifications">
      <h3>Streamer-Benachrichtigungen</h3>
      <div class="table-controls">
        <button @click="toggleAllStreamers(true)" class="btn btn-secondary">Alle aktivieren</button>
        <button @click="toggleAllStreamers(false)" class="btn btn-secondary">Alle deaktivieren</button>
      </div>
      
      <div class="streamer-table">
        <table>
          <thead>
            <tr>
              <th>Streamer</th>
              <th>
                Online
                <div class="th-tooltip">Benachrichtigung bei Stream-Start</div>
              </th>
              <th>
                Offline
                <div class="th-tooltip">Benachrichtigung bei Stream-Ende</div>
              </th>
              <th>
                Updates
                <div class="th-tooltip">Benachrichtigung bei Titel/Kategorie-Änderungen</div>
              </th>
              <th>
                Favoriten
                <div class="th-tooltip">Benachrichtigung bei Favoriten-Spielen</div>
              </th>
              <th>Aktionen</th>
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
              </td>
              <td>
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_online"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_online: streamer.notify_online })"
                />
              </td>
              <td>
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_offline"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_offline: streamer.notify_offline })"
                />
              </td>
              <td>
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_update"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_update: streamer.notify_update })"
                />
              </td>
              <td>
                <input 
                  type="checkbox" 
                  v-model="streamer.notify_favorite_category"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_favorite_category: streamer.notify_favorite_category })"
                />
              </td>
              <td>
                <button 
                  @click="toggleAllForStreamer(streamer.streamer_id, true)" 
                  class="btn btn-sm btn-secondary"
                  style="margin-right: 8px;"
                >Alle an</button>
                <button 
                  @click="toggleAllForStreamer(streamer.streamer_id, false)" 
                  class="btn btn-sm btn-secondary"
                >Alle aus</button>
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

// Data kopieren, um sie im Formular zu verwenden
const data = ref({
  notificationUrl: props.settings.notification_url || '',
  notificationsEnabled: props.settings.notifications_enabled !== false,
  notifyOnlineGlobal: props.settings.notify_online_global !== false,
  notifyOfflineGlobal: props.settings.notify_offline_global !== false, 
  notifyUpdateGlobal: props.settings.notify_update_global !== false,
  notifyFavoriteCategoryGlobal: props.settings.notify_favorite_category_global !== false
})

const showTooltip = ref(false)
let tooltipTimeout: number | undefined = undefined

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
      notify_favorite_category_global: data.value.notifyFavoriteCategoryGlobal
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
</script>

<style scoped>
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

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  font-weight: normal;
}

.checkbox-group input[type="checkbox"] {
  margin-right: 8px;
}

.input-with-tooltip {
  position: relative;
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
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary {
  background-color: #9146FF;
  color: white;
}

.btn-secondary {
  background-color: #3a3a3a;
  color: white;
}

.btn-sm {
  padding: 4px 8px;
  font-size: 0.875rem;
}

.streamer-notifications {
  margin-top: 30px;
}

.table-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.streamer-table table {
  width: 100%;
  border-collapse: collapse;
  background-color: #1f1f23;
  border-radius: 8px;
  overflow: hidden;
}

.streamer-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.streamer-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  overflow: hidden;
}

.streamer-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.streamer-table th,
.streamer-table td {
  padding: 12px 15px;
  text-align: left;
  border-bottom: 1px solid #333;
}

.streamer-table th {
  background-color: #18181b;
  font-weight: 500;
  color: #ccc;
}

.streamer-table tr:last-child td {
  border-bottom: none;
}

.th-tooltip {
  font-size: 0.8rem;
  font-weight: normal;
  color: #aaa;
  margin-top: 4px;
}
</style>
