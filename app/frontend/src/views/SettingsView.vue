<template>
  <div class="settings-view">
    <div class="settings-container">
      <div v-if="isLoading" class="loading-indicator">
        <div class="spinner"></div>
        <p>Loading settings...</p>
      </div>
      
      <div v-else>
        <!-- Verbesserte Tab-Navigation -->
        <div class="settings-tabs-wrapper">
          <div class="settings-tabs">
            <button 
              v-for="tab in availableTabs" 
              :key="tab.id"
              @click="activeTab = tab.id" 
              :class="{ active: activeTab === tab.id }"
              class="tab-button"
              :aria-selected="activeTab === tab.id"
              role="tab"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>
        
        <!-- Tab Content -->
        <div class="tab-content">
          <!-- Notifications Tab -->
          <div v-if="activeTab === 'notifications'" class="tab-pane" role="tabpanel">
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
          <div v-if="activeTab === 'recording'" class="tab-pane" role="tabpanel">
            <RecordingSettingsPanel
              :settings="recordingSettings"
              :streamer-settings="recordingStreamerSettings"
              :active-recordings="activeRecordings"
              @update="handleUpdateRecordingSettings"
              @update-streamer="handleUpdateStreamerRecordingSettings"
              @stop-recording="handleStopRecording"
              @cleanup-recordings="handleCleanupRecordings"
            />
          </div>
          
          <!-- Favorites Tab -->
          <div v-if="activeTab === 'favorites'" class="tab-pane" role="tabpanel">
            <FavoritesSettingsPanel />
          </div>
          
          <!-- PWA Tab -->
          <div v-if="activeTab === 'pwa'" class="tab-pane" role="tabpanel">
            <PWAPanel />
          </div>
          
          <!-- Logging Tab -->
          <!-- <div v-if="activeTab === 'logging'" class="tab-pane" role="tabpanel">
            <LoggingPanel />
          </div> -->
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useWebSocket } from '@/composables/useWebSocket'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import FavoritesSettingsPanel from '@/components/settings/FavoritesSettingsPanel.vue'
import PWAPanel from '@/components/settings/PWAPanel.vue'
// import LoggingPanel from '@/components/settings/LoggingPanel.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'
import type { RecordingSettings, StreamerRecordingSettings, ActiveRecording } from '@/types/recording'

// Verfügbare Tabs als Array für einfachere Verwaltung
const availableTabs = computed(() => [
  { id: 'notifications', label: 'Notifications' },
  { id: 'recording', label: 'Recording' },
  { id: 'favorites', label: 'Favorite Games' },
  { id: 'pwa', label: 'PWA & Mobile' }
  // { id: 'logging', label: 'Logging & Monitoring' }
])

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
  cleanupOldRecordings
} = useRecordingSettings()

const activeTab = ref('notifications')
const notificationStreamerSettings = ref<StreamerNotificationSettings[]>([])
const isLoading = ref(true)
const isSaving = ref(false)
// Poll for active recordings
const pollingInterval: number | undefined = undefined

onMounted(async () => {
  isLoading.value = true
  try {
    // Load notification settings
    await fetchNotificationSettings()
    notificationStreamerSettings.value = await getNotificationStreamerSettings()
    
    // Load recording settings with better error handling
    try {
      await fetchRecordingSettings()
    } catch (e) {
      console.error("Failed to load recording settings:", e)
    }
    
    try {
      await fetchRecordingStreamerSettings()
    } catch (e) {
      console.error("Failed to load recording streamer settings:", e) 
    }
    
    try {
      await fetchActiveRecordings()
    } catch (e) {
      console.error("Failed to load active recordings:", e)
    }
    
    // Active recordings are now updated via WebSocket
    
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    isLoading.value = false
  }
})

// WebSocket integration for real-time active recordings updates  
const { messages } = useWebSocket()

watch(messages, (newMessages) => {
  if (newMessages.length === 0) return
  
  const latestMessage = newMessages[newMessages.length - 1]
  
  // Handle active recordings updates via WebSocket
  if (latestMessage.type === 'active_recordings_update') {
    activeRecordings.value = latestMessage.data || []
  } else if (latestMessage.type === 'recording_started' || latestMessage.type === 'recording_stopped') {
    // Refresh when recording state changes
    fetchActiveRecordings()
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

const handleCleanupRecordings = async (streamerId: number) => {
  try {
    const success = await cleanupOldRecordings(streamerId)
    if (success) {
      alert('Old recordings cleaned up successfully.')
    } else {
      alert('Failed to clean up recordings.')
    }
  } catch (error) {
    alert(error instanceof Error ? error.message : 'Failed to clean up recordings')
  }
}
</script>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.settings-container {
  max-width: 1200px;
  min-width: 800px;
  width: 100%;
  margin: 0 auto;
  padding: 20px;
  box-sizing: border-box;
}

.loading-indicator {
  text-align: center;
  padding: 40px;
  color: #aaa;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #ccc;
  border-top-color: #9146FF;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Verbesserte Tab-Navigation mit Scroll-Schatten für kleine Bildschirme */
.settings-tabs-wrapper {
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}

.settings-tabs-wrapper::before,
.settings-tabs-wrapper::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 24px;
  z-index: 2;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.settings-tabs-wrapper::before {
  left: 0;
  background: linear-gradient(90deg, rgba(24, 24, 27, 0.95), transparent);
}

.settings-tabs-wrapper::after {
  right: 0;
  background: linear-gradient(-90deg, rgba(24, 24, 27, 0.95), transparent);
}

.settings-tabs-wrapper.scroll-start::before {
  opacity: 1;
}

.settings-tabs-wrapper.scroll-end::after {
  opacity: 1;
}

.settings-tabs {
  display: flex;
  border-bottom: 1px solid #333;
  overflow-x: auto;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE/Edge */
  position: relative;
  padding-bottom: 1px;
}

.settings-tabs::-webkit-scrollbar {
  display: none; /* Chrome/Safari/Opera */
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
  white-space: nowrap;
  flex-shrink: 0;
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
  width: 100%;
  min-width: 760px;
  box-sizing: border-box;
}

/* Tablet-optimierung */
@media (max-width: 1024px) and (min-width: 641px) {
  .settings-container {
    min-width: 700px;
  }
  
  .tab-content {
    min-width: 660px;
  }
}

/* Mobile-optimierung */
@media (max-width: 640px) {
  .settings-container {
    min-width: unset;
    padding: 12px;
  }
  
  .tab-content {
    min-width: unset;
  }
  
  .settings-tabs {
    justify-content: flex-start;
  }
  
  .tab-button {
    padding: 10px 16px;
    font-size: 0.9rem;
  }
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
