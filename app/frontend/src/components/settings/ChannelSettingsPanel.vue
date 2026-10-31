<template>
  <div class="channel-settings-panel">
    <p v-if="loading" role="status">Kanaleinstellungen werden geladen...</p>
    <div v-else-if="loadError" role="alert" class="error-message">
      <p>{{ loadError }}</p>
      <button class="btn btn-secondary" @click="load">Erneut versuchen</button>
    </div>
    <template v-else>
      <nav v-if="!streamerId" class="channel-links settings-group" aria-label="Kanaleinstellungen öffnen">
        <h2>Einzelnen Kanal einstellen</h2>
        <p>Qualität, Dateinamen, Aufbewahrung und Benachrichtigungen stellst du direkt beim Kanal ein.</p>
        <RouterLink v-for="channel in recording.streamerSettings.value" :key="channel.streamer_id"
          :to="{ path: `/streamers/${channel.streamer_id}`, query: { tab: 'settings' } }" class="btn btn-secondary">
          {{ channel.username }}
        </RouterLink>
        <p v-if="!recording.streamerSettings.value.length">Noch keine Kanäle vorhanden.</p>
      </nav>
      <p v-if="mutationError" role="alert" class="error-message">{{ mutationError }}</p>
      <RecordingSettingsPanel
        :context="context"
        :show-overrides="false"
        :settings="recording.settings.value"
        :streamer-settings="recordingChannels"
        :active-recordings="activeRecordings"
        @update-streamer="updateRecording"
        @stop-recording="stopRecording"
      />
      <NotificationSettingsPanel
        v-if="notifications.settings.value"
        :context="context"
        :show-overrides="false"
        :settings="notifications.settings.value"
        :streamer-settings="notificationChannels"
        @update-streamer-settings="updateNotifications"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import RecordingSettingsPanel from './RecordingSettingsPanel.vue'
import NotificationSettingsPanel from './NotificationSettingsPanel.vue'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import { useToast } from '@/composables/useToast'
import type { StreamerRecordingSettings } from '@/types/recording'
import type { StreamerNotificationSettings } from '@/types/settings'

const props = defineProps<{ streamerId?: number }>()
const emit = defineEmits<{
  recordingUpdated: [settings: Partial<StreamerRecordingSettings>]
  notificationsUpdated: [settings: Partial<StreamerNotificationSettings>]
}>()
const recording = useRecordingSettings()
const notifications = useNotificationSettings()
const toast = useToast()
const loading = ref(true)
const loadError = ref('')
const mutationError = ref('')
const context = computed(() => props.streamerId ? 'channel' : 'manage')
const recordingChannels = computed(() => recording.streamerSettings.value.filter(channel => !props.streamerId || channel.streamer_id === props.streamerId))
const notificationChannels = computed(() => notifications.streamerSettings.value.filter(channel => !props.streamerId || channel.streamer_id === props.streamerId))
const activeRecordings = computed(() => recording.activeRecordings.value.filter(item => !props.streamerId || item.streamer_id === props.streamerId))

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    await Promise.all([
      recording.fetchSettings(), recording.fetchStreamerSettings(), recording.fetchActiveRecordings(),
      notifications.fetchSettings(), notifications.getStreamerSettings()
    ])
    if (recording.error.value || !notifications.settings.value) throw new Error('Settings unavailable')
  } catch {
    loadError.value = 'Kanaleinstellungen konnten nicht geladen werden.'
  } finally {
    loading.value = false
  }
}
async function mutate(action: () => Promise<unknown>, success: string) {
  mutationError.value = ''
  try {
    await action()
    toast.success(success)
  } catch {
    mutationError.value = 'Änderung fehlgeschlagen. Bitte erneut versuchen.'
    toast.error(mutationError.value)
  }
}
function updateRecording(id: number, settings: Partial<StreamerRecordingSettings>) {
  return mutate(async () => {
    await recording.updateStreamerSettings(id, settings)
    if (id === props.streamerId) emit('recordingUpdated', settings)
  }, 'Aufnahmeeinstellungen gespeichert')
}
function updateNotifications(id: number, settings: Partial<StreamerNotificationSettings>) {
  return mutate(async () => {
    await notifications.updateStreamerSettings(id, settings)
    await notifications.getStreamerSettings()
    if (id === props.streamerId) emit('notificationsUpdated', settings)
  }, 'Benachrichtigungen gespeichert')
}
function stopRecording(id: number) {
  return mutate(async () => {
    if (!await recording.stopRecording(id)) throw new Error('Stop failed')
  }, 'Aufnahme gestoppt')
}
onMounted(load)
defineExpose({ reload: load })
</script>

<style scoped>
.channel-settings-panel {
  display: grid;
  gap: var(--spacing-5);
  min-width: 0;
}
.channel-links .btn {
  margin: var(--spacing-2);
}
</style>
