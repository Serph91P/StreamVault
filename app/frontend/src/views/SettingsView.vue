<template>
  <div class="settings-container">
    <div v-if="isLoading" class="loading-indicator">
      <p>Loading settings...</p>
    </div>
    
    <div v-else>
      <!-- Tab Navigation -->
      <div class="settings-tabs">
        <button 
          @click="activeTab = 'notifications'" 
          :class="{ active: activeTab === 'notifications' }"
          class="tab-button"
        >
          Notifications
        </button>
        <button 
          @click="activeTab = 'recording'" 
          :class="{ active: activeTab === 'recording' }"
          class="tab-button"
        >
          Recording
        </button>
        <button 
          @click="activeTab = 'favorites'" 
          :class="{ active: activeTab === 'favorites' }"
          class="tab-button"
        >
          Favorite Games
        </button>
      </div>
      
      <!-- Tab Content -->
      <div class="tab-content">
        <!-- Notifications Tab -->
        <div v-if="activeTab === 'notifications'" class="tab-pane">
          <NotificationSettingsPanel 
            :settings="notificationSettings || {
              notification_url: '',
              notifications_enabled: true,
              apprise_docs_url: '',
              notify_online_global: true,
              notify_offline_global: true,
              notify_update_global: true,
              notify_favorite_category_global: false
            }"
            :streamer-settings="notificationStreamerSettings"
            @update-settings="handleUpdateNotificationSettings"
            @update-streamer-settings="handleUpdateStreamerNotificationSettings"
            @test-notification="handleTestNotification"
          />
        </div>
        
        <!-- Recording Tab -->
        <div v-if="activeTab === 'recording'" class="tab-pane">
          <RecordingSettingsPanel
            :settings="recordingSettings"
            :streamer-settings="recordingStreamerSettings"
            :active-recordings="activeRecordings"
            @update="handleUpdateRecordingSettings"
            @update-streamer="handleUpdateStreamerRecordingSettings"
            @test-recording="handleTestRecording"
            @stop-recording="handleStopRecording"
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import FavoritesSettingsPanel from '@/components/settings/FavoritesSettingsPanel.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'
import type { RecordingSettings, StreamerRecordingSettings, ActiveRecording } from '@/types/recording'

const { 
  settings: notificationSettings, 
  fetchSettings: fetchNotificationSettings, 
  updateSettings: updateNotificationSettings, 
  getStreamerSettings: getNotificationStreamerSettings, 
  updateStreamerSettings: updateStreamerNotificationSettings 
} = useNotificationSettings()

const {
  settings: recordingSettings,
  streamerSettings: recordingStreamerSettings,
  activeRecordings,
  fetchSettings: fetchRecordingSettings,
  updateSettings: updateRecordingSettings,
  fetchStreamerSettings: fetchRecordingStreamerSettings,
  updateStreamerSettings: updateStreamerRecordingSettings,
  fetchActiveRecordings,
  stopRecording,
  testRecording
} = useRecordingSettings()

const activeTab = ref('notifications')
const notificationStreamerSettings = ref<StreamerNotificationSettings[]>([])
const isLoading = ref(true)
const isSaving = ref(false)

// Poll for active recordings
let pollingInterval: number | undefined = undefined

onMounted(async () => {
  isLoading.value = true
  try {
    // Load notification settings
    await fetchNotificationSettings()
    notificationStreamerSettings.value = await getNotificationStreamerSettings()
    
    // Load recording settings
    await fetchRecordingSettings()
    await fetchRecordingStreamerSettings()
    await fetchActiveRecordings()
    
    // Start polling for active recordings
    pollingInterval = window.setInterval(() => {
      fetchActiveRecordings()
    }, 5000) // Poll every 5 seconds
    
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    isLoading.value = false
  }
})

onBeforeUnmount(() => {
  // Clear polling interval when component is unmounted
  if (pollingInterval) {
    clearInterval(pollingInterval)
  }
})

// Notification handlers
const handleUpdateNotificationSettings = async (newSettings: Partial<NotificationSettings>) => {
  try {
    isSaving.value = true
    await updateNotificationSettings(newSettings)
    alert('Notification settings saved successfully!')
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to update notification settings')
  } finally {
    isSaving.value = false
  }
}

const handleUpdateStreamerNotificationSettings = async (
  streamerId: number, 
  settings: Partial<StreamerNotificationSettings>
) => {
  try {
    const updatedSettings = await updateStreamerNotificationSettings(streamerId, settings)
    const index = notificationStreamerSettings.value.findIndex(s => s.streamer_id === streamerId)
    if (index !== -1) {
      notificationStreamerSettings.value[index] = {
        ...notificationStreamerSettings.value[index],
        ...updatedSettings
      }
    }
  } catch (error) {
    console.error('Failed to update streamer notification settings:', error)
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

// Recording handlers
const handleUpdateRecordingSettings = async (newSettings: RecordingSettings) => {
  try {
    isSaving.value = true
    await updateRecordingSettings(newSettings)
    alert('Recording settings saved successfully!')
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to update recording settings')
  } finally {
    isSaving.value = false
  }
}

const handleUpdateStreamerRecordingSettings = async (
  streamerId: number, 
  settings: Partial<StreamerRecordingSettings>
) => {
  try {
    await updateStreamerRecordingSettings(streamerId, settings)
  } catch (error) {
    console.error('Failed to update streamer recording settings:', error)
  }
}

const handleTestRecording = async (streamerId: number) => {
  try {
    const success = await testRecording(streamerId)
    if (success) {
      alert('Test recording started. Check the "Active Recordings" section.')
    } else {
      alert('Failed to start test recording.')
    }
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to start test recording')
  }
}

const handleStopRecording = async (streamerId: number) => {
  try {
    const success = await stopRecording(streamerId)
    if (success) {
      alert('Recording stopped successfully.')
    } else {
      alert('Failed to stop recording.')
    }
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to stop recording')
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

.checkbox-group label {
  display: flex;
  align-items: flex-start;
  font-weight: normal;
  text-align: left;
}

.checkbox-group input[type="checkbox"] {
  margin-right: 8px;
  margin-top: 4px;
}
</style>