<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import Tooltip from '@/components/Tooltip.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

const { settings, fetchSettings, updateSettings, getStreamerSettings, updateStreamerSettings } = useNotificationSettings()

interface ComponentData {
  notificationUrl: string
  notificationsEnabled: boolean
  appriseDocsUrl: string
  notifyOnlineGlobal: boolean
  notifyOfflineGlobal: boolean
  notifyUpdateGlobal: boolean
  streamerSettings: StreamerNotificationSettings[]
}

const data = ref<ComponentData>({
  notificationUrl: '',
  notificationsEnabled: true,
  appriseDocsUrl: '',
  notifyOnlineGlobal: true,
  notifyOfflineGlobal: true,
  notifyUpdateGlobal: true,
  streamerSettings: []
})

onMounted(async () => {
  await fetchSettings()
  const settingsData = settings.value
  data.value = {
    notificationUrl: settingsData?.notification_url || '',
    notificationsEnabled: settingsData?.notifications_enabled ?? true,
    appriseDocsUrl: settingsData?.apprise_docs_url || '',
    notifyOnlineGlobal: settingsData?.notify_online_global ?? true,
    notifyOfflineGlobal: settingsData?.notify_offline_global ?? true,
    notifyUpdateGlobal: settingsData?.notify_update_global ?? true,
    streamerSettings: await getStreamerSettings()
  }
})

const saveSettings = async () => {
  await updateSettings({
    notification_url: data.value.notificationUrl,
    notifications_enabled: data.value.notificationsEnabled,
    notify_online_global: data.value.notifyOnlineGlobal,
    notify_offline_global: data.value.notifyOfflineGlobal,
    notify_update_global: data.value.notifyUpdateGlobal
  })
}

const handleStreamerSettingsUpdate = async (
  streamerId: number, 
  streamerSettings: Partial<StreamerNotificationSettings>
) => {
  const updatedSettings = await updateStreamerSettings(streamerId, streamerSettings)
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
  data.value.streamerSettings.forEach((streamer: StreamerNotificationSettings) => {
    toggleAllForStreamer(streamer.streamer_id, enabled)
  })
}

// Add showTooltip ref
const showTooltip = ref(false)
// Change the tooltip timer type
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

// Clean up timeout on component unmount
onUnmounted(() => {
  if (tooltipTimeout) {
    window.clearTimeout(tooltipTimeout)
  }
})
</script>

<template>
  <div class="settings-container">
    <h2 class="settings-title">Notification Settings</h2>
    
    <!-- Global Settings -->
    <div class="settings-form">
      <div class="form-group">
        <label>Notification Service URL:</label>
        <div class="input-with-tooltip">
          <input 
            v-model="data.notificationUrl" 
            placeholder="e.g., ntfy://topic or telegram://bot_token/chat_id"
            class="form-control"
            @focus="showTooltip = true"
          />
          <div 
            v-if="showTooltip" 
            class="tooltip-wrapper"
            @mouseenter="handleTooltipMouseEnter"
            @mouseleave="handleTooltipMouseLeave"
          >
            <Tooltip>
              Check the <a 
                href="https://github.com/caronc/apprise/wiki"
                target="_blank" 
                rel="noopener noreferrer"
                @click.stop
                class="tooltip-link"
              >Apprise Documentation</a> for supported services and URL formats
            </Tooltip>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label>
          <input type="checkbox" v-model="data.notificationsEnabled" />
          Enable Notifications
        </label>
      </div>

      <button @click="saveSettings" class="btn btn-primary">Save Settings</button>
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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="streamer in data.streamerSettings" :key="streamer.streamer_id">
              <td class="streamer-info">
                <span class="streamer-name">{{ streamer.username }}</span>
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
                <button 
                  @click="toggleAllForStreamer(streamer.streamer_id, true)" 
                  class="btn btn-sm btn-secondary"
                >Enable All</button>
                <button 
                  @click="toggleAllForStreamer(streamer.streamer_id, false)" 
                  class="btn btn-sm btn-secondary"
                >Disable All</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>