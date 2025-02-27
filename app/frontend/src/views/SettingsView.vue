<template>
  <div class="settings-container">
    <h2 class="settings-title">Einstellungen</h2>
    
    <!-- Sub-Navigation -->
    <div class="settings-tabs">
      <button 
        class="tab-button" 
        :class="{ 'active': activeTab === 'notifications' }"
        @click="activeTab = 'notifications'"
      >
        Benachrichtigungen
      </button>
      <button 
        class="tab-button" 
        :class="{ 'active': activeTab === 'favorites' }"
        @click="activeTab = 'favorites'"
      >
        Favoriten
      </button>
    </div>

    <!-- Notification Settings Tab -->
    <div v-if="activeTab === 'notifications'" class="tab-content">
      <NotificationSettingsPanel 
        :settings="notificationData" 
        :streamerSettings="streamerSettings"
        @update-settings="saveSettings"
        @update-streamer-settings="handleStreamerSettingsUpdate"
        @test-notification="testNotification"
      />
    </div>

    <!-- Favorites Settings Tab -->
    <div v-if="activeTab === 'favorites'" class="tab-content">
      <FavoritesSettingsPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import FavoritesSettingsPanel from '@/components/settings/FavoritesSettingsPanel.vue'

// Aktiver Tab
const activeTab = ref('notifications')

// Notification Settings
const { settings, fetchSettings, updateSettings, getStreamerSettings, updateStreamerSettings } = useNotificationSettings()

const notificationData = ref({
  notificationUrl: '',
  notificationsEnabled: true,
  appriseDocsUrl: '',
  notifyOnlineGlobal: true,
  notifyOfflineGlobal: true,
  notifyUpdateGlobal: true,
  notifyFavoriteCategoryGlobal: true
})

const streamerSettings = ref([])

onMounted(async () => {
  await fetchSettings()
  const settingsData = settings.value
  notificationData.value = {
    notificationUrl: settingsData?.notification_url || '',
    notificationsEnabled: settingsData?.notifications_enabled ?? true,
    appriseDocsUrl: settingsData?.apprise_docs_url || '',
    notifyOnlineGlobal: settingsData?.notify_online_global ?? true,
    notifyOfflineGlobal: settingsData?.notify_offline_global ?? true,
    notifyUpdateGlobal: settingsData?.notify_update_global ?? true,
    notifyFavoriteCategoryGlobal: settingsData?.notify_favorite_category_global ?? true
  }
  streamerSettings.value = await getStreamerSettings()
})

const saveSettings = async (newSettings) => {
  await updateSettings(newSettings)
  await fetchSettings()
}

const handleStreamerSettingsUpdate = async (streamerId, settings) => {
  await updateStreamerSettings(streamerId, settings)
}

const testNotification = async () => {
  try {
    const response = await fetch('/api/settings/test-notification', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to send test notification')
    }

    alert('Test notification sent successfully!')
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to send test notification')
  }
}
</script>

<style scoped>
.settings-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.settings-title {
  margin-bottom: 20px;
  font-size: 1.8rem;
}

.settings-tabs {
  display: flex;
  margin-bottom: 20px;
  border-bottom: 1px solid #3a3a3a;
}

.tab-button {
  padding: 10px 20px;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  color: #aaaaaa;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
}

.tab-button:hover {
  color: #ffffff;
}

.tab-button.active {
  color: #9146FF;
  border-bottom-color: #9146FF;
}

.tab-content {
  background-color: #18181b;
  border-radius: 8px;
  padding: 20px;
}
</style>