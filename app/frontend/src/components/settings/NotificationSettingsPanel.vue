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
            placeholder="e.g., discord://webhook1,telegram://bot_token
            class="form-control"
            :class="{ 'is-invalid': !isValidNotificationUrl && data.notificationUrl.trim() }"
            @focus="showTooltip = true"
          />
          <div 
            v-if="!isValidNotificationUrl && data.notificationUrl.trim()" 
            class="invalid-feedback"
          >
            Please enter a valid notification service URL (e.g., discord://webhook_id/webhook_token)
          </div>
          <div 
            v-if="showTooltip" 
            class="tooltip-wrapper"
            @mouseenter="handleTooltipMouseEnter"
            @mouseleave="handleTooltipMouseLeave"
          >
            <Tooltip>
              StreamVault supports 100+ notification services including Discord, Telegram, Ntfy, 
              Pushover, Slack, and more. Check the 
              <a 
                href="https://github.com/caronc/apprise/wiki#notification-services"
                target="_blank" 
                rel="noopener noreferrer"
                @click.stop
                class="tooltip-link"
              >Apprise Documentation</a> for supported services and URL formats.
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
            <tr v-for="streamer in streamerSettings" :key="streamer.streamer_id">
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
import Tooltip from '@/components/Tooltip.vue'
import type { StreamerNotificationSettings } from '@/types/settings'

// Props
const props = defineProps({
  settings: {
    type: Object,
    required: true
  },
  streamerSettings: {
    type: Array,
    required: true
  }
})

// Emits
const emit = defineEmits(['update-settings', 'update-streamer-settings', 'test-notification'])

// Data kopieren, um sie im Formular zu verwenden
const data = ref({ ...props.settings })

// Validierung und Speichern - Hier kopieren Sie die Logik aus der alten SettingsView
const KNOWN_SCHEMES = [
  'discord', 'telegram', 'tgram', 'slack', 'pushover', 'mailto',
  'ntfy', 'matrix', 'twilio', 'msteams', 'slack', 'gchat', 'ligne',
  'signal', 'whatsapp', 'rocket', 'pushbullet', 'apprise', 'http',
  'https', 'twitter', 'slack', 'dbus'
]

const isSaving = ref(false)
const showTooltip = ref(false)
let tooltipTimeout: number | undefined = undefined

const isValidNotificationUrl = computed(() => {
  const url = data.value.notificationUrl.trim()
  
  // Empty URL is considered valid (though not for saving)
  if (!url) return true
  
  // Handle multiple URLs separated by comma
  if (url.includes(',')) {
    return url.split(',')
      .every(part => {
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

const canSave = computed(() => {
  return isValidNotificationUrl.value && 
         (data.value.notificationUrl.trim() !== '' || !data.value.notificationsEnabled)
})

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

// Clean up timeout on component unmount
onUnmounted(() => {
  if (tooltipTimeout) {
    window.clearTimeout(tooltipTimeout)
  }
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
  
  emit('update-streamer-settings', streamerId, {
    notify_online: enabled,
    notify_offline: enabled,
    notify_update: enabled,
    notify_favorite_category: enabled
  })
}

const toggleAllStreamers = async (enabled: boolean) => {
  if (!props.streamerSettings) return
  
  for (const streamer of props.streamerSettings) {
    if (!streamer?.streamer_id) continue
    
    toggleAllForStreamer(Number(streamer.streamer_id), enabled)
  }
}

const testNotification = () => {
  emit('test-notification')
}