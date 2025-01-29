<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import Tooltip from '@/components/Tooltip.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

const { settings, updateSettings, getStreamerSettings, updateStreamerSettings } = useNotificationSettings()

interface ComponentData {
  notificationUrl: string
  notificationsEnabled: boolean
  appriseDocsUrl: string
  streamerSettings: StreamerNotificationSettings[]
}

const data = ref<ComponentData>({
  notificationUrl: '',
  notificationsEnabled: true,
  appriseDocsUrl: '',
  streamerSettings: []
})

onMounted(async () => {
  const settingsData = await settings.value as NotificationSettings
  data.value = {
    notificationUrl: settingsData?.notification_url || '',
    notificationsEnabled: settingsData?.notifications_enabled ?? true,
    appriseDocsUrl: settingsData?.apprise_docs_url || '',
    streamerSettings: await getStreamerSettings()
  }
})

const saveSettings = async () => {
  await updateSettings({
    notification_url: data.value.notificationUrl,
    notifications_enabled: data.value.notificationsEnabled,
    apprise_docs_url: data.value.appriseDocsUrl
  } as NotificationSettings)
}

const handleStreamerSettingsUpdate = async (
  streamerId: number, 
  settings: Partial<StreamerNotificationSettings>
) => {
  const updatedSettings = await updateStreamerSettings(streamerId, settings)
  const index = data.value.streamerSettings.findIndex(s => s.streamer_id === streamerId)
  if (index !== -1) {
    data.value.streamerSettings[index] = updatedSettings
  }
}

const toggleAllForStreamer = (streamerId: number, enabled: boolean) => {
  handleStreamerSettingsUpdate(streamerId, {
    notify_online: enabled,
    notify_offline: enabled,
    notify_update: enabled
  })
}

const toggleAllStreamers = (enabled: boolean) => {
  data.value.streamerSettings.forEach(streamer => {
    toggleAllForStreamer(streamer.streamer_id, enabled)
  })
}
</script>

<template>
  <div class="settings-container">
    <h2>Notification Settings</h2>
    
    <div class="settings-form">
      <div class="form-group">
        <label>Notification Service URL:</label>
        <div class="input-with-tooltip">
          <input 
            v-model="data.notificationUrl" 
            placeholder="e.g., ntfy://topic or telegram://bot_token/chat_id"
            class="form-control"
          />
          <Tooltip>
            Check the <a 
              :href="data.appriseDocsUrl" 
              target="_blank" 
              rel="noopener noreferrer"
            >Apprise Documentation</a> for supported services and URL formats
          </Tooltip>
        </div>
      </div>

      <div class="form-group">
        <label>
          <input 
            type="checkbox" 
            v-model="data.notificationsEnabled"
          />
          Enable Notifications
        </label>
      </div>

      <button @click="saveSettings" class="btn btn-primary">
        Save Settings
      </button>
    </div>

    <div class="streamer-notifications">
    <div class="streamer-controls">
      <h3>Per-Streamer Settings</h3>
      <div class="global-controls">
        <button @click="toggleAllStreamers(true)" class="btn btn-secondary">
          Enable All
        </button>
        <button @click="toggleAllStreamers(false)" class="btn btn-secondary">
          Disable All
        </button>
      </div>
    </div>

    <div v-for="streamer in data.streamerSettings" 
         :key="streamer.streamer_id" 
         class="streamer-card">
      <div class="streamer-header">
        <h4>{{ streamer.username }}</h4>
        <div class="streamer-controls">
          <button @click="toggleAllForStreamer(streamer.streamer_id, true)" 
                  class="btn btn-sm">
            Enable All
          </button>
          <button @click="toggleAllForStreamer(streamer.streamer_id, false)" 
                  class="btn btn-sm">
            Disable All
          </button>
        </div>
      </div>

      <div class="notification-toggles">
        <label class="toggle">
          <input type="checkbox" 
                 v-model="streamer.notify_online"
                 @change="updateStreamerSettings(streamer.streamer_id, { notify_online: streamer.notify_online })" />
          Stream Online
        </label>

        <label class="toggle">
          <input type="checkbox" 
                 v-model="streamer.notify_offline"
                 @change="updateStreamerSettings(streamer.streamer_id, { notify_offline: streamer.notify_offline })" />
          Stream Offline
        </label>

        <label class="toggle">
          <input type="checkbox" 
                 v-model="streamer.notify_update"
                 @change="updateStreamerSettings(streamer.streamer_id, { notify_update: streamer.notify_update })" />
          Channel Updates
        </label>
      </div>
    </div>
  </div>
</div>
</template>