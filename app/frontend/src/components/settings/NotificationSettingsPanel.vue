<template>
    <template v-if="context === 'global'">
      <div class="settings-group">
        <div class="settings-group-header">
          <h3 class="settings-group-title">
            <svg><use href="#icon-send" /></svg>
            Zustellung
          </h3>
          <p class="settings-group-desc">Ziel der Benachrichtigungen und globaler Hauptschalter</p>
        </div>

        <div>
          <BaseInput
            v-model="data.notificationUrl"
            label="URL des Benachrichtigungsdienstes"
            placeholder="Apprise-URL eingeben"
            :error="notificationUrlError"
            hint="Apprise-URL verwenden. Mehrere Dienste durch Kommas trennen."
            @update:model-value="handleInput"
            @blur="handleBlur"
          />
          <details
            ref="urlHelp"
            class="notification-url-help"
            @keydown.esc.stop.prevent="closeUrlHelp"
          >
            <summary>Hilfe zur Benachrichtigungs-URL</summary>
            <p>
              StreamVault unterstützt über 100 Benachrichtigungsdienste, darunter Discord, Telegram, Ntfy,
              Pushover und Slack. Unterstützte Dienste und URL-Formate stehen in der
              <a
                href="https://github.com/caronc/apprise/wiki#notification-services"
                target="_blank"
                rel="noopener noreferrer"
                @click.stop
              >Apprise-Dokumentation</a>.
            </p>
          </details>
        </div>

        <div class="form-check">
          <label>
            <input type="checkbox" v-model="data.notificationsEnabled" />
            Benachrichtigungen aktivieren
          </label>
        </div>
      </div>

      <div class="settings-group">
        <div class="settings-group-header">
          <h3 class="settings-group-title">
            <svg><use href="#icon-radio" /></svg>
            Streamereignisse
          </h3>
          <p class="settings-group-desc">Bei welchen Ereignissen soll eine Nachricht gesendet werden?</p>
        </div>
        <div class="checkbox-group">
          <label>
            <input type="checkbox" v-model="data.notifyOnlineGlobal" />
            Stream startet
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyOfflineGlobal" />
            Stream endet
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyUpdateGlobal" />
            Titel oder Kategorie ändern sich
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyFavoriteCategoryGlobal" />
            Stream in einer Lieblingskategorie
          </label>
        </div>
      </div>

      <!-- System Notification Settings (advanced) -->
      <div class="settings-group">
        <div class="settings-group-header">
          <h3 class="settings-group-title">
            <svg><use href="#icon-video" /></svg>
            Aufnahmeereignisse
          </h3>
          <p class="settings-group-desc">
            Externe Benachrichtigungen zu Aufnahmen einstellen, zum Beispiel für Discord oder Telegram.
          </p>
        </div>
        <div class="checkbox-group">
          <label>
            <input type="checkbox" v-model="data.notifyRecordingStarted" />
            Aufnahme gestartet
            <span class="label-hint">(kann viele Nachrichten erzeugen)</span>
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyRecordingFailed" />
            Aufnahme fehlgeschlagen
            <span class="label-hint label-recommended">(empfohlen, um Fehler zu bemerken)</span>
          </label>
          <label>
            <input type="checkbox" v-model="data.notifyRecordingCompleted" />
            Aufnahme abgeschlossen
            <span class="label-hint">(kann viele Nachrichten erzeugen)</span>
          </label>
        </div>
      </div>

      <div class="form-actions">
        <button
          @click="saveSettings"
          class="btn btn-primary"
          :disabled="isSaving || !canSave"
        >
          {{ isSaving ? 'Wird gespeichert...' : 'Einstellungen speichern' }}
        </button>
        <p class="diagnostics-note">
          Zustellungstests findest du in der Admin-Diagnose.
        </p>
      </div>

    </template>
    <!-- Channel controls are never part of global settings. -->
    <div v-if="context !== 'global'" class="settings-group streamer-notifications">
      <div class="settings-group-header">
        <h3 class="settings-group-title">
          <svg><use href="#icon-users" /></svg>
          {{ context === 'manage' ? 'Benachrichtigungen für alle Kanäle' : 'Benachrichtigungen für diesen Kanal' }}
        </h3>
        <p class="settings-group-desc">{{ context === 'manage' ? 'Online-, Offline- und Änderungsereignisse für alle Kanäle schalten. Lieblingskategorien bleiben unverändert.' : 'Diese Einstellungen überschreiben die globalen Streamereignisse.' }}</p>
      </div>
      <div v-if="context === 'manage'" class="table-controls">
        <BaseButton variant="secondary" @click="toggleAllStreamers(true)">Für alle aktivieren</BaseButton>
        <BaseButton variant="secondary" @click="toggleAllStreamers(false)">Für alle deaktivieren</BaseButton>
      </div>

      <div v-if="context === 'channel'" class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Kanal</th>
              <th v-if="showOverrides">
                Online
                <div class="th-tooltip">Bei Streamstart benachrichtigen</div>
              </th>
              <th v-if="showOverrides">
                Offline
                <div class="th-tooltip">Bei Streamende benachrichtigen</div>
              </th>
              <th v-if="showOverrides">
                Änderungen
                <div class="th-tooltip">Bei Titel- oder Kategorieänderungen benachrichtigen</div>
              </th>
              <th v-if="showOverrides">
                Lieblingskategorien
                <div class="th-tooltip">Bei Streams in Lieblingskategorien benachrichtigen</div>
              </th>
              <th>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="streamer in typedStreamerSettings" :key="streamer.streamer_id">
              <td class="streamer-info">
                <div class="streamer-avatar" v-if="streamer.profile_image_url">
                  <img
                    :src="streamer.profile_image_url"
                    :alt="streamer.username || ''"
                  />
                </div>
                <span class="streamer-name">{{ streamer.username || 'Unbekannter Kanal' }}</span>
              </td>              <td v-if="showOverrides" data-label="Online">
                <input
                  type="checkbox"
                  :aria-label="`Bei Streamstart von ${streamer.username || 'Kanal'} benachrichtigen`"
                  v-model="streamer.notify_online"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_online: streamer.notify_online })"
                />
              </td>
              <td v-if="showOverrides" data-label="Offline">
                <input
                  type="checkbox"
                  :aria-label="`Bei Streamende von ${streamer.username || 'Kanal'} benachrichtigen`"
                  v-model="streamer.notify_offline"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_offline: streamer.notify_offline })"
                />
              </td>
              <td v-if="showOverrides" data-label="Änderungen">
                <input
                  type="checkbox"
                  :aria-label="`Bei Änderungen von ${streamer.username || 'Kanal'} benachrichtigen`"
                  v-model="streamer.notify_update"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_update: streamer.notify_update })"
                />
              </td>
              <td v-if="showOverrides" data-label="Lieblingskategorien">
                <input
                  type="checkbox"
                  :aria-label="`Bei Lieblingskategorien von ${streamer.username || 'Kanal'} benachrichtigen`"
                  v-model="streamer.notify_favorite_category"
                  @change="updateStreamerSettings(streamer.streamer_id, { notify_favorite_category: streamer.notify_favorite_category })"
                />
              </td>              <td class="actions-cell">
                <div class="btn-group">
                  <button
                    @click="toggleAllForStreamer(streamer.streamer_id, true)"
                    class="btn btn-sm btn-secondary"
                  >Alle an</button>
                  <button
                    @click="toggleAllForStreamer(streamer.streamer_id, false)"
                    class="btn btn-sm btn-secondary"
                  >Alle aus</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted, type PropType } from 'vue'
import { UI } from '@/config/constants'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

// Props
const props = defineProps({
  showOverrides: { type: Boolean, default: true },
  context: {
    type: String as PropType<'global' | 'channel' | 'manage'>,
    default: 'global'
  },
  settings: {
    type: Object as () => NotificationSettings,
    required: true
  },
  streamerSettings: {
    type: Array as () => StreamerNotificationSettings[],
    required: true
  }
})

// Typed version of streamerSettings to fix TS errors
const typedStreamerSettings = computed(() => {
  return props.streamerSettings as StreamerNotificationSettings[]
})

// Emits
const emit = defineEmits(['update-settings', 'update-streamer-settings'])

// Data kopieren, um sie im Formular zu verwenden
const data = ref({
  notificationUrl: props.settings.notification_url || '',
  // SECURITY: Only enable if URL is configured - prevents errors when no URL is set
  notificationsEnabled: props.settings.notifications_enabled === true && !!props.settings.notification_url,
  notifyOnlineGlobal: props.settings.notify_online_global !== false,
  notifyOfflineGlobal: props.settings.notify_offline_global !== false,
  notifyUpdateGlobal: props.settings.notify_update_global !== false,
  notifyFavoriteCategoryGlobal: props.settings.notify_favorite_category_global !== false,
  // System notification settings (NEW - Migration 028)
  notifyRecordingStarted: props.settings.notify_recording_started !== undefined ? props.settings.notify_recording_started : false,
  notifyRecordingFailed: props.settings.notify_recording_failed !== undefined ? props.settings.notify_recording_failed : true,
  notifyRecordingCompleted: props.settings.notify_recording_completed !== undefined ? props.settings.notify_recording_completed : false
})

// Add these new refs for validation
const showValidationError = ref(false)
const inputTimeout = ref<number | null>(null)
const urlHelp = ref<HTMLDetailsElement | null>(null)

const closeUrlHelp = () => {
  if (!urlHelp.value?.open) return
  urlHelp.value.open = false
  urlHelp.value.querySelector('summary')?.focus()
}

// Handle input with debounce
const handleInput = () => {
  // Clear existing timeout
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value)
  }

  // Set a new timeout to show validation after typing stops
  inputTimeout.value = window.setTimeout(() => {
    showValidationError.value = true
  }, UI.VALIDATION_DEBOUNCE_MS)
}

// Handle blur event (when user clicks outside the input)
const handleBlur = () => {
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value)
  }
  showValidationError.value = true
}

// Cleanup timeout on component unmount
onUnmounted(() => {
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value)
  }
})

// Validierung und Speichern
const KNOWN_SCHEMES = [
  'discord', 'telegram', 'tgram', 'slack', 'pushover', 'mailto',
  'ntfy', 'matrix', 'twilio', 'msteams', 'slack', 'gchat', 'ligne',
  'signal', 'whatsapp', 'rocket', 'pushbullet', 'apprise', 'http',
  'https', 'twitter', 'slack', 'dbus'
]

const isSaving = ref(false)

const isValidNotificationUrl = computed(() => {
  const url = data.value.notificationUrl.trim()

  // Empty URL is considered valid (though not for saving)
  if (!url) return true

  // Handle multiple URLs separated by comma
  if (url.includes(',')) {
    return url.split(',')
      .every((part: string) => {
        const trimmedPart = part.trim()
        return trimmedPart === '' || validateSingleUrl(trimmedPart)
      })
  }

  return validateSingleUrl(url)
})

const notificationUrlError = computed(() => {
  if (!showValidationError.value || isValidNotificationUrl.value || !data.value.notificationUrl.trim()) {
    return undefined
  }

  return 'Please enter a valid URL (e.g., discord://webhook_id/webhook_token)'
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

// Can Save Computed
const canSave = computed(() => {
  return isValidNotificationUrl.value &&
         (data.value.notificationUrl.trim() !== '' || !data.value.notificationsEnabled)
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
      notify_favorite_category_global: data.value.notifyFavoriteCategoryGlobal,
      // System notification settings (Migration 028)
      notify_recording_started: data.value.notifyRecordingStarted,
      notify_recording_failed: data.value.notifyRecordingFailed,
      notify_recording_completed: data.value.notifyRecordingCompleted
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

  const settingsUpdate: Partial<StreamerNotificationSettings> = {
    notify_online: enabled,
    notify_offline: enabled,
    notify_update: enabled,
    ...(props.context === 'channel' ? { notify_favorite_category: enabled } : {})
  }

  emit('update-streamer-settings', streamerId, settingsUpdate)
}

const toggleAllStreamers = (enabled: boolean) => {
  if (!props.streamerSettings) return

  for (const streamer of typedStreamerSettings.value) {
    if (!streamer?.streamer_id) continue

    toggleAllForStreamer(streamer.streamer_id, enabled)
  }
}

</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.notification-url-help {
  margin-block: var(--spacing-3);
  color: var(--text-secondary);

  summary {
    min-height: 44px;
    padding-block: var(--spacing-3);
    cursor: pointer;
  }

  p {
    margin: 0;
    padding-block: var(--spacing-2);
  }

  a {
    color: var(--primary-color);
    text-decoration: underline;
  }
}

// ============================================================================
// NOTIFICATION SETTINGS PANEL - Unified Design
// Most styles inherited from global _settings-panels.scss
// ============================================================================


// ============================================================================
// CHECKBOX GROUP - Better spacing
// ============================================================================

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-4;  // More spacing between checkboxes

  label {
    display: flex;
    align-items: flex-start;
    gap: v.$spacing-3;
    padding: v.$spacing-3;
    background: var(--background-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    transition: v.$transition-all;
    cursor: pointer;

    &:hover {
      border-color: var(--primary-color);
      background: var(--background-hover);
    }

    input[type="checkbox"] {
      margin-top: 2px;  // Align with text
      flex-shrink: 0;
    }
  }

  @include m.respond-below('lg') {
    gap: v.$spacing-2;

    label {
      padding: v.$spacing-2 v.$spacing-3;
      min-height: 44px;
    }
  }

  @include m.respond-below('md') {
    gap: v.$spacing-3;

    label {
      padding: v.$spacing-3;
      min-height: 44px;  // Touch-friendly
      flex-wrap: wrap;  // Allow content to wrap on mobile

      // Stack label text and hint vertically
      .label-hint {
        flex-basis: 100%;
        margin-top: v.$spacing-1;
        margin-left: calc(18px + v.$spacing-3);  // Align with text after checkbox
      }
    }
  }
}

.form-check label {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-3);
  min-height: 44px;
  cursor: pointer;
}

.data-table td > input[type="checkbox"] {
  width: 44px;
  height: 44px;
  cursor: pointer;
}

// ============================================================================
// FORM ACTIONS - Better button alignment
// ============================================================================

.form-actions {
  display: flex;
  gap: v.$spacing-3;
  flex-wrap: wrap;

  .btn {
    flex: 1;
    min-width: 150px;

    &:last-child {
      margin-left: 0 !important;  // Remove inline margin
    }
  }
}

.diagnostics-note {
  flex: 2;
  min-width: 240px;
  margin: 0;
  color: var(--text-secondary);
  font-size: v.$text-sm;
  line-height: var(--leading-relaxed);
}

// ============================================================================
// STREAMER NOTIFICATIONS TABLE - Better spacing
// ============================================================================

.streamer-notifications {
  margin-top: v.$spacing-6;

  .table-wrapper {
    margin-top: v.$spacing-4;  // Space from table controls
  }

  .data-table th,
  .data-table td {
    vertical-align: middle;
  }

  .actions-cell {
    width: 116px;
  }
}

.btn-group {
  display: inline-flex;
  align-items: center;
  min-width: 96px;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--background-darker);

  .btn {
    min-height: 44px;
    min-width: 44px;
    padding: 0 var(--spacing-2);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    line-height: 1;
  }
}

// ============================================================================
// RESPONSIVE
// ============================================================================

@include m.respond-below('md') {
  .form-actions {
    flex-direction: column;
    gap: v.$spacing-3;

    .btn {
      width: 100%;
      min-width: 100%;
      flex: none;
    }
  }

  .streamer-notifications {
    h2 {
      font-size: v.$text-xl;
    }
  }
}
</style>
