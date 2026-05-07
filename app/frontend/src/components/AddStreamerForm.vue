<template>
  <form @submit.prevent="validateAndSubmit" class="streamer-form">
    <div class="input-group">
      <input
        type="text"
        v-model="username"
        :disabled="isLoading || isValidating"
        placeholder="Enter Twitch username"
        required
        class="input-field interactive-element"
        @blur="validateUsername"
      >
      <BaseButton
        type="button"
        variant="secondary"
        :loading="isValidating"
        :disabled="isLoading || !username.trim()"
        class="validate-button interactive-element"
        @click="validateUsername"
      >
        Check
      </BaseButton>
    </div>

    <!-- Settings only shown after username is validated -->
    <div v-if="isValid && streamerInfo" class="settings-panel content-section">
      <div class="streamer-preview">
        <img
          v-if="streamerInfo.profile_image_url"
          :src="streamerInfo.profile_image_url"
          alt="Profile"
          class="profile-image"
        >
        <div class="streamer-info">
          <div class="streamer-name">{{ streamerInfo.display_name }}</div>
          <div class="streamer-details" v-if="streamerInfo.description">
            {{ streamerInfo.description }}
          </div>
        </div>
      </div>

      <StreamerSettingsFields v-model="settings" :disabled="isLoading" />
    </div>

    <div class="form-actions">
      <BaseButton
        type="submit"
        variant="primary"
        :loading="isLoading"
        :disabled="isValidating || !isValid"
      >
        Add Streamer
      </BaseButton>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import StreamerSettingsFields from '@/components/streamers/StreamerSettingsFields.vue'
import { buildDefaultState } from '@/schemas/streamerSettings.schema'
import { useToast } from '@/composables/useToast'

interface StreamerInfo {
  display_name?: string
  profile_image_url?: string
  description?: string
}

const emit = defineEmits<{
  (e: 'streamer-added'): void
}>()

const toast = useToast()

const username = ref('')
const isLoading = ref(false)
const isValidating = ref(false)
const isValid = ref(false)
const streamerInfo = ref<StreamerInfo | null>(null)

// Schema-driven reactive state: { quality, notifications: {...}, recording: {...} }
const settings = reactive<Record<string, unknown>>(buildDefaultState())

const validateUsername = async () => {
  if (!username.value.trim()) return

  isValidating.value = true
  isValid.value = false
  streamerInfo.value = null

  try {
    const response = await fetch(
      `/api/streamers/validate/${username.value.trim().toLowerCase()}`,
      { credentials: 'include' },
    )
    const data = await response.json()

    if (response.ok && data.valid) {
      isValid.value = true
      streamerInfo.value = data.streamer_info
      toast.success(`@${username.value.trim()} is a valid Twitch user`)
    } else {
      isValid.value = false
      toast.error(data.message || 'Invalid Twitch username')
    }
  } catch (error) {
    isValid.value = false
    toast.error('Error checking username')
    console.error('Error:', error)
  } finally {
    isValidating.value = false
  }
}

const validateAndSubmit = () => {
  if (!isValid.value) {
    validateUsername()
    return
  }
  addStreamer()
}

const addStreamer = async () => {
  if (!username.value.trim() || !isValid.value) return

  isLoading.value = true

  // Emit immediately so the parent (modal/view) can close. Backend WebSocket
  // event "streamer.added" + toast handle user feedback.
  emit('streamer-added')

  try {
    const cleanUsername = username.value.trim().toLowerCase()

    const response = await fetch(`/api/streamers/${cleanUsername}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    })

    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      toast.error(data?.message || 'Failed to add streamer')
    }
  } catch (error) {
    toast.error('Error connecting to server')
    console.error('Error:', error)
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.input-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.validate-button {
  padding: 10px 16px;
  font-weight: 600;
}

.settings-panel {
  margin-top: 1.5rem;
  padding: 1rem;
}

.streamer-preview {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.profile-image {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--color-primary);
}

.streamer-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 1.05rem;
}

.streamer-details {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.form-actions {
  margin-top: 1.5rem;
  display: flex;
  justify-content: flex-end;
}
</style>
