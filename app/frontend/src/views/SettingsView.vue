<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import Tooltip from '@/components/Tooltip.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

const { settings, fetchSettings, updateSettings, getStreamerSettings, updateStreamerSettings } = useNotificationSettings()

const KNOWN_SCHEMES = [
  'discord', 'telegram', 'tgram', 'slack', 'pushover', 'mailto',
  'ntfy', 'matrix', 'twilio', 'msteams', 'slack', 'gchat', 'ligne',
  'signal', 'whatsapp', 'rocket', 'pushbullet', 'apprise', 'http',
  'https', 'twitter', 'slack', 'dbus'
];

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

const isSaving = ref(false);

const isValidNotificationUrl = computed(() => {
  const url = data.value.notificationUrl.trim();
  
  // Empty URL is considered valid (though not for saving)
  if (!url) return true;
  
  // Handle multiple URLs separated by comma
  if (url.includes(',')) {
    return url.split(',')
      .every(part => {
        const trimmedPart = part.trim();
        return trimmedPart === '' || validateSingleUrl(trimmedPart);
      });
  }
  
  return validateSingleUrl(url);
});

const validateSingleUrl = (url: string): boolean => {
  // Basic URL structure check
  if (!url.includes('://')) return false;
  
  // Extract scheme
  const scheme = url.split('://')[0].toLowerCase();
  
  // Check against known schemes
  if (KNOWN_SCHEMES.includes(scheme)) return true;
  
  // Allow custom schemes that follow the pattern: xxx://
  return /^[a-zA-Z]+:\/\/.+/.test(url);
};

const canSave = computed(() => {
  return isValidNotificationUrl.value && 
         (data.value.notificationUrl.trim() !== '' || !data.value.notificationsEnabled);
});

const saveSettings = async () => {
  if (isSaving.value) return;
  
  try {
    isSaving.value = true;
    await updateSettings({
      notification_url: data.value.notificationUrl,
      notifications_enabled: data.value.notificationsEnabled,
      notify_online_global: data.value.notifyOnlineGlobal,
      notify_offline_global: data.value.notifyOfflineGlobal,
      notify_update_global: data.value.notifyUpdateGlobal
    });
    alert('Settings saved successfully!');
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to save settings');
  } finally {
    isSaving.value = false;
  }
};

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

const toggleAllStreamers = async (enabled: boolean) => {
  for (const streamer of data.value.streamerSettings) {
    await handleStreamerSettingsUpdate(streamer.streamer_id, {
      notify_online: enabled,
      notify_offline: enabled,
      notify_update: enabled
    })
  }
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

const testNotification = async () => {
  try {
    const response = await fetch('/api/settings/test-notification', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to send test notification');
    }

    alert('Test notification sent successfully!');
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to send test notification');
  }
};
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
            placeholder="e.g., discord://webhook_id/webhook_token"
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
          Enable Notifications
        </label>
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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="streamer in data.streamerSettings" :key="streamer.streamer_id">
              <td class="streamer-info">
                <!-- Only show image if profile_image_url exists -->
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

<style scoped>
.form-control.is-invalid {
  border-color: #dc3545;
}

.invalid-feedback {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  font-size: 0.875em;
  color: #dc3545;
}
</style>