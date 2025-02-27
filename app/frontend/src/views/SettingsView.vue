<template>
  <div class="settings-container">
    <div v-if="isLoading" class="loading-indicator">
      <p>Einstellungen werden geladen...</p>
    </div>
    
    <div v-else>
      <!-- Tab Navigation -->
      <div class="settings-tabs">
        <button 
          @click="activeTab = 'notifications'" 
          :class="{ active: activeTab === 'notifications' }"
          class="tab-button"
        >
          Benachrichtigungen
        </button>
        <button 
          @click="activeTab = 'favorites'" 
          :class="{ active: activeTab === 'favorites' }"
          class="tab-button"
        >
          Favoriten-Spiele
        </button>
      </div>
      
      <!-- Tab Content -->
      <div class="tab-content">
        <!-- Notifications Tab -->
        <div v-if="activeTab === 'notifications'" class="tab-pane">
          <NotificationSettingsPanel 
            :settings="settings || {
              notification_url: '',
              notifications_enabled: true,
              apprise_docs_url: '',
              notify_online_global: true,
              notify_offline_global: true,
              notify_update_global: true,
              notify_favorite_category_global: false
            }"
            :streamer-settings="streamerSettings"
            @update-settings="handleUpdateSettings"
            @update-streamer-settings="handleUpdateStreamerSettings"
            @test-notification="handleTestNotification"
          />
        </div>
        
        <!-- Favorites Tab -->
        <div v-if="activeTab === 'favorites'" class="tab-pane">
          <FavoritesSettingsPanel />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import FavoritesSettingsPanel from '@/components/settings/FavoritesSettingsPanel.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

const { settings, fetchSettings, updateSettings, getStreamerSettings, updateStreamerSettings } = useNotificationSettings()

const activeTab = ref('notifications')
const streamerSettings = ref<StreamerNotificationSettings[]>([])
const isLoading = ref(true)
const isSaving = ref(false)

onMounted(async () => {
  isLoading.value = true
  try {
    await fetchSettings()
    streamerSettings.value = await getStreamerSettings()
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    isLoading.value = false
  }
})

const handleUpdateSettings = async (newSettings: Partial<NotificationSettings>) => {
  try {
    isSaving.value = true
    await updateSettings(newSettings)
    alert('Settings saved successfully!')
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to update settings')
  } finally {
    isSaving.value = false
  }
}

const handleUpdateStreamerSettings = async (
  streamerId: number, 
  settings: Partial<StreamerNotificationSettings>
) => {
  try {
    const updatedSettings = await updateStreamerSettings(streamerId, settings)
    const index = streamerSettings.value.findIndex(s => s.streamer_id === streamerId)
    if (index !== -1) {
      streamerSettings.value[index] = {
        ...streamerSettings.value[index],
        ...updatedSettings
      }
    }
  } catch (error) {
    console.error('Failed to update streamer settings:', error)
  }
}

const handleTestNotification = async () => {
  try {
    const response = await fetch('/api/settings/test-notification', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.loading-indicator {
  text-align: center;
  padding: 40px;
  color: #aaa;
}

.settings-tabs {
  display: flex;
  border-bottom: 1px solid #333;
  margin-bottom: 20px;
}

.tab-button {
  padding: 12px 20px;
  background: none;
  border: none;
  cursor: pointer;
  color: #ccc;
  font-size: 1rem;
  border-bottom: 3px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.tab-button.active {
  color: #9146FF;
  border-bottom-color: #9146FF;
}

.tab-button:hover:not(.active) {
  color: #fff;
  border-bottom-color: #555;
}

.tab-content {
  min-height: 400px;
}
</style>