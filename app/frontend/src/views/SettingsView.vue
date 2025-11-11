<template>
  <div class="settings-view">
    <!-- Header -->
    <div class="view-header">
      <div class="header-content">
        <h1 class="page-title">
          <svg class="icon-title">
            <use href="#icon-settings" />
          </svg>
          Settings
        </h1>
        <p class="page-subtitle">Configure your StreamVault preferences and options</p>
      </div>

      <div class="header-actions" v-if="hasUnsavedChanges">
        <button @click="resetChanges" class="btn-action btn-secondary" v-ripple>
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
          Discard
        </button>
        <button @click="saveAllChanges" class="btn-action btn-primary" v-ripple>
          <svg class="icon">
            <use href="#icon-check" />
          </svg>
          Save Changes
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <LoadingSkeleton type="card" />
      <LoadingSkeleton type="card" />
      <LoadingSkeleton type="card" />
    </div>

    <!-- Settings Layout -->
    <div v-else class="settings-layout">
      <!-- Sidebar Navigation -->
      <aside class="settings-sidebar">
        <nav class="settings-nav">
          <button
            v-for="section in sections"
            :key="section.id"
            @click="activeSection = section.id"
            :class="{ active: activeSection === section.id }"
            class="nav-item"
            v-ripple
          >
            <svg class="nav-icon">
              <use :href="`#icon-${section.icon}`" />
            </svg>
            <div class="nav-content">
              <span class="nav-label">{{ section.label }}</span>
              <span class="nav-description">{{ section.description }}</span>
            </div>
            <svg v-if="activeSection === section.id" class="nav-indicator">
              <use href="#icon-chevron-right" />
            </svg>
          </button>
        </nav>
      </aside>

      <!-- Settings Content -->
      <main class="settings-content">
        <!-- Notifications Settings -->
        <div v-if="activeSection === 'notifications'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-bell" />
              </svg>
              Notifications
            </h2>
            <p class="section-description">
              Configure notification preferences for stream events
            </p>
          </div>

          <NotificationSettingsPanel
            :settings="notificationSettings || defaultNotificationSettings"
            :streamer-settings="notificationStreamerSettings"
            @update-settings="handleUpdateNotificationSettings"
            @update-streamer-settings="handleUpdateStreamerNotificationSettings"
            @test-notification="handleTestNotification"
          />
        </div>

        <!-- Recording Settings -->
        <div v-if="activeSection === 'recording'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-video" />
              </svg>
              Recording
            </h2>
            <p class="section-description">
              Manage recording quality, storage, and behavior
            </p>
          </div>

          <RecordingSettingsPanel
            :settings="recordingSettings"
            :streamer-settings="recordingStreamerSettings"
            :active-recordings="activeRecordings"
            @update="handleUpdateRecordingSettings"
            @update-streamer="handleUpdateStreamerRecordingSettings"
            @stop-recording="handleStopRecording"
          />
        </div>

        <!-- Favorites Settings -->
        <div v-if="activeSection === 'favorites'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-star" />
              </svg>
              Favorite Games
            </h2>
            <p class="section-description">
              Set favorite game categories for priority notifications
            </p>
          </div>

          <FavoritesSettingsPanel />
        </div>

        <!-- Appearance Settings -->
        <div v-if="activeSection === 'appearance'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-palette" />
              </svg>
              Appearance
            </h2>
            <p class="section-description">
              Customize the look and feel of your application
            </p>
          </div>

          <GlassCard>
            <div class="card-content">
              <div class="setting-item">
                <div class="setting-info">
                  <label class="setting-label">Theme</label>
                  <p class="setting-description">Choose your preferred color scheme</p>
                </div>
                <div class="setting-control">
                  <select v-model="theme" class="select-input">
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                  </select>
                </div>
              </div>

              <div class="setting-item">
                <div class="setting-info">
                  <label class="setting-label">Animations</label>
                  <p class="setting-description">Enable or disable interface animations</p>
                </div>
                <div class="setting-control">
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="animationsEnabled" />
                    <span class="toggle-slider"></span>
                  </label>
                </div>
              </div>
            </div>
          </GlassCard>
        </div>

        <!-- PWA Settings -->
        <div v-if="activeSection === 'pwa'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-smartphone" />
              </svg>
              PWA & Mobile
            </h2>
            <p class="section-description">
              Progressive Web App and mobile-specific settings
            </p>
          </div>

          <PWAPanel />
        </div>

        <!-- Advanced Settings -->
        <div v-if="activeSection === 'advanced'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-sliders" />
              </svg>
              Advanced
            </h2>
            <p class="section-description">
              Advanced configuration and maintenance options
            </p>
          </div>

          <GlassCard>
            <div class="card-content">
              <div class="setting-item">
                <div class="setting-info">
                  <label class="setting-label">Debug Mode</label>
                  <p class="setting-description">Enable detailed logging and debugging</p>
                </div>
                <div class="setting-control">
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="debugMode" />
                    <span class="toggle-slider"></span>
                  </label>
                </div>
              </div>

              <div class="setting-item">
                <div class="setting-info">
                  <label class="setting-label">Enable Animations</label>
                  <p class="setting-description">Show animated transitions, hover effects, and recording pulse</p>
                </div>
                <div class="setting-control">
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="animationsEnabled" @change="toggleAnimations" />
                    <span class="toggle-slider"></span>
                  </label>
                </div>
              </div>

              <div class="setting-item">
                <div class="setting-info">
                  <label class="setting-label">Clear Cache</label>
                  <p class="setting-description">Remove cached data and reload application</p>
                </div>
                <div class="setting-control">
                  <button @click="clearCache" class="btn-outline btn-danger" v-ripple>
                    Clear All Cache
                  </button>
                </div>
              </div>
            </div>
          </GlassCard>
        </div>

        <!-- About Settings -->
        <div v-if="activeSection === 'about'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-info" />
              </svg>
              About
            </h2>
            <p class="section-description">
              Application information and version details
            </p>
          </div>

          <GlassCard>
            <div class="card-content">
              <div class="about-content">
                <div class="about-logo">
                  <svg class="logo-icon">
                    <use href="#icon-video" />
                  </svg>
                </div>
                <h3 class="about-title">StreamVault</h3>
                <p class="about-version">Version 1.0.0</p>
                <p class="about-description">
                  Automated stream recording and management system for Twitch content creators.
                </p>
                <div class="about-links">
                  <a href="https://github.com/yourusername/streamvault" target="_blank" class="about-link">
                    <svg class="icon">
                      <use href="#icon-github" />
                    </svg>
                    GitHub
                  </a>
                  <a href="#" class="about-link">
                    <svg class="icon">
                      <use href="#icon-book" />
                    </svg>
                    Documentation
                  </a>
                </div>
              </div>
            </div>
          </GlassCard>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useWebSocket } from '@/composables/useWebSocket'
import { useTheme } from '@/composables/useTheme'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import GlassCard from '@/components/cards/GlassCard.vue'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import FavoritesSettingsPanel from '@/components/settings/FavoritesSettingsPanel.vue'
import PWAPanel from '@/components/settings/PWAPanel.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'
import type { RecordingSettings } from '@/types/recording'

// Settings sections
const sections = [
  {
    id: 'notifications',
    label: 'Notifications',
    description: 'Stream alerts & updates',
    icon: 'bell'
  },
  {
    id: 'recording',
    label: 'Recording',
    description: 'Quality & storage',
    icon: 'video'
  },
  {
    id: 'favorites',
    label: 'Favorite Games',
    description: 'Priority categories',
    icon: 'star'
  },
  {
    id: 'appearance',
    label: 'Appearance',
    description: 'Theme & visuals',
    icon: 'palette'
  },
  {
    id: 'pwa',
    label: 'PWA & Mobile',
    description: 'Mobile app settings',
    icon: 'smartphone'
  },
  {
    id: 'advanced',
    label: 'Advanced',
    description: 'Technical settings',
    icon: 'sliders'
  },
  {
    id: 'about',
    label: 'About',
    description: 'App information',
    icon: 'info'
  }
]

// State
const activeSection = ref('notifications')
const isLoading = ref(true)
const hasUnsavedChanges = ref(false)

// Theme management - use global theme composable
const { theme, setTheme } = useTheme()

// Appearance settings
const animationsEnabled = ref(true)

// Advanced settings
const debugMode = ref(false)

// Notification settings composable
const {
  settings: notificationSettings,
  fetchSettings: fetchNotificationSettings,
  updateSettings: updateNotificationSettings,
  getStreamerSettings: getNotificationStreamerSettings,
  updateStreamerSettings: updateStreamerNotificationSettings
} = useNotificationSettings()

// Recording settings composable
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

const notificationStreamerSettings = ref<StreamerNotificationSettings[]>([])

// Default notification settings
const defaultNotificationSettings = {
  notification_url: '',
  notifications_enabled: true,
  apprise_docs_url: '',
  notify_online_global: true,
  notify_offline_global: true,
  notify_update_global: true,
  notify_favorite_category_global: false
}

// Load all settings
async function loadAllSettings() {
  isLoading.value = true
  try {
    // Load notification settings
    await fetchNotificationSettings()
    notificationStreamerSettings.value = await getNotificationStreamerSettings()

    // Load recording settings
    try {
      await fetchRecordingSettings()
      await fetchRecordingStreamerSettings()
      await fetchActiveRecordings()
    } catch (error) {
      console.error('Failed to load recording settings:', error)
    }
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    isLoading.value = false
  }
}

// WebSocket integration for real-time updates
const { messages } = useWebSocket()

watch(messages, (newMessages) => {
  if (newMessages.length === 0) return

  const latestMessage = newMessages[newMessages.length - 1]

  if (latestMessage.type === 'active_recordings_update') {
    activeRecordings.value = latestMessage.data || []
  } else if (latestMessage.type === 'recording_started' || latestMessage.type === 'recording_stopped') {
    fetchActiveRecordings()
  }
})

// Watch theme changes from dropdown and apply via setTheme
watch(theme, (newTheme) => {
  // Only call setTheme if it's a valid theme value
  if (newTheme === 'dark' || newTheme === 'light') {
    setTheme(newTheme)
  }
})

// Notification handlers
async function handleUpdateNotificationSettings(newSettings: Partial<NotificationSettings>) {
  try {
    await updateNotificationSettings(newSettings)
  } catch (error) {
    console.error('Failed to update notification settings:', error)
  }
}

async function handleUpdateStreamerNotificationSettings(
  streamerId: number,
  settings: Partial<StreamerNotificationSettings>
) {
  try {
    await updateStreamerNotificationSettings(streamerId, settings)
    notificationStreamerSettings.value = await getNotificationStreamerSettings()
  } catch (error) {
    console.error('Failed to update streamer notification settings:', error)
  }
}

function handleTestNotification() {
  console.log('Test notification triggered')
}

// Recording handlers
async function handleUpdateRecordingSettings(newSettings: RecordingSettings) {
  try {
    await updateRecordingSettings(newSettings)
  } catch (error) {
    console.error('Failed to update recording settings:', error)
  }
}

async function handleUpdateStreamerRecordingSettings(streamerId: number, settings: any) {
  try {
    await updateStreamerRecordingSettings(streamerId, settings)
    await fetchRecordingStreamerSettings()
  } catch (error) {
    console.error('Failed to update streamer recording settings:', error)
  }
}

async function handleStopRecording(recordingId: number) {
  try {
    await stopRecording(recordingId)
    await fetchActiveRecordings()
  } catch (error) {
    console.error('Failed to stop recording:', error)
  }
}

// Advanced actions
function clearCache() {
  if (confirm('This will clear all cached data and reload the application. Continue?')) {
    localStorage.clear()
    sessionStorage.clear()
    window.location.reload()
  }
}

function toggleAnimations() {
  // Save to localStorage
  localStorage.setItem('animationsEnabled', animationsEnabled.value.toString())
  
  // Apply or remove 'no-animations' class from document
  if (animationsEnabled.value) {
    document.documentElement.classList.remove('no-animations')
  } else {
    document.documentElement.classList.add('no-animations')
  }
}

function saveAllChanges() {
  hasUnsavedChanges.value = false
  // Save logic handled by individual panels
}

function resetChanges() {
  hasUnsavedChanges.value = false
  loadAllSettings()
}

// Initialize
onMounted(() => {
  loadAllSettings()
  
  // Load animation preference from localStorage
  const savedAnimationsEnabled = localStorage.getItem('animationsEnabled')
  if (savedAnimationsEnabled !== null) {
    animationsEnabled.value = savedAnimationsEnabled === 'true'
  }
  
  // Apply animation state on mount
  if (!animationsEnabled.value) {
    document.documentElement.classList.add('no-animations')
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.settings-view {
  padding: var(--spacing-6) var(--spacing-4);
  max-width: 1600px;
  margin: 0 auto;
  min-height: 100vh;
}

// Header
.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-6);
  gap: var(--spacing-4);
  flex-wrap: wrap;
}

.header-content {
  flex: 1;
  min-width: 250px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  font-size: var(--text-3xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-2) 0;

  .icon-title {
    width: 32px;
    height: 32px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--spacing-3);
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  border: none;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }

  &.btn-primary {
    background: var(--primary-color);
    color: white;

    &:hover {
      background: var(--primary-600);
      box-shadow: var(--shadow-md);
    }
  }

  &.btn-secondary {
    background: var(--background-card);
    color: var(--text-primary);
    border: 1px solid var(--border-color);

    &:hover {
      border-color: var(--primary-color);
    }
  }
}

// Loading
.loading-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--spacing-5);
}

// Settings Layout
.settings-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: var(--spacing-6);
  align-items: start;
}

// Sidebar
.settings-sidebar {
  position: sticky;
  top: var(--spacing-6);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  padding: var(--spacing-2);
}

.settings-nav {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.05);
    color: var(--text-primary);
  }

  &.active {
    background: var(--primary-color);
    color: white;

    .nav-icon {
      stroke: white;
    }

    .nav-description {
      color: rgba(255, 255, 255, 0.8);
    }

    .nav-indicator {
      stroke: white;
    }
  }
}

.nav-icon {
  width: 20px;
  height: 20px;
  stroke: currentColor;
  fill: none;
  flex-shrink: 0;
}

.nav-content {
  flex: 1;
  min-width: 0;
}

.nav-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  line-height: 1.4;
}

.nav-description {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  line-height: 1.3;
}

.nav-indicator {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  fill: none;
  flex-shrink: 0;
}

// Settings Content
.settings-content {
  min-width: 0;
}

.settings-section {
  animation: fade-in v.$duration-300 v.$ease-out;
}

.section-header {
  margin-bottom: var(--spacing-6);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  font-size: var(--text-2xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-2) 0;

  .section-icon {
    width: 28px;
    height: 28px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.section-description {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0;
}

// Settings Cards
.settings-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  overflow: hidden;
  margin-bottom: var(--spacing-5);
}

.card-content {
  padding: var(--spacing-6);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-4);
  padding: var(--spacing-4) 0;
  border-bottom: 1px solid var(--border-color);

  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  &:first-child {
    padding-top: 0;
  }
}

.setting-info {
  flex: 1;
  min-width: 0;
}

.setting-label {
  display: block;
  font-size: var(--text-base);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
}

.setting-description {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.4;
}

.setting-control {
  flex-shrink: 0;
}

// Form Controls
.select-input,
.text-input {
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  min-width: 200px;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    border-color: var(--primary-color);
  }

  &:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
  }
}

// Toggle Switch
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 24px;
  cursor: pointer;

  input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .toggle-slider {
    position: absolute;
    inset: 0;
    background: var(--background-darker);
    border: 2px solid var(--border-color);
    border-radius: var(--radius-full);
    transition: all v.$duration-200 v.$ease-out;

    &::before {
      content: '';
      position: absolute;
      height: 16px;
      width: 16px;
      left: 2px;
      top: 2px;
      background: var(--text-tertiary);
      border-radius: 50%;
      transition: all v.$duration-200 v.$ease-out;
    }
  }

  input:checked + .toggle-slider {
    background: var(--primary-color);
    border-color: var(--primary-color);

    &::before {
      background: white;
      transform: translateX(24px);
    }
  }
}

.btn-outline {
  padding: var(--spacing-2) var(--spacing-4);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &.btn-danger {
    border-color: var(--danger-color);
    color: var(--danger-color);

    &:hover {
      background: var(--danger-color);
      color: white;
    }
  }
}

// About Section
.about-content {
  text-align: center;
  padding: var(--spacing-6) 0;
}

.about-logo {
  display: flex;
  justify-content: center;
  margin-bottom: var(--spacing-4);

  .logo-icon {
    width: 64px;
    height: 64px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.about-title {
  font-size: var(--text-2xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-1) 0;
}

.about-version {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin: 0 0 var(--spacing-4) 0;
}

.about-description {
  font-size: var(--text-base);
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 500px;
  margin: 0 auto var(--spacing-6);
}

.about-links {
  display: flex;
  gap: var(--spacing-3);
  justify-content: center;
}

.about-link {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-5);
  min-height: 44px;  /* Touch-friendly target */
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  color: var(--text-primary);
  text-decoration: none;
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    border-color: var(--primary-color);
    background: rgba(var(--primary-color-rgb), 0.1);
    color: var(--primary-color);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  }

  &:active {
    transform: translateY(0);
  }
}

// Animations
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// Responsive
@media (max-width: 1024px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }

  .settings-sidebar {
    position: static;
    overflow-x: auto;
    padding: var(--spacing-3);
  }

  .settings-nav {
    flex-direction: row;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;

    &::-webkit-scrollbar {
      display: none;
    }
  }

  .nav-item {
    flex-shrink: 0;
    min-width: 180px;
  }

  .nav-indicator {
    display: none;
  }
}

@media (max-width: 640px) {
  .settings-view {
    padding: var(--spacing-4) var(--spacing-3);
  }

  .page-title {
    font-size: var(--text-2xl);
  }

  .header-actions {
    width: 100%;

    .btn-action {
      flex: 1;
      min-height: 44px;  // Touch-friendly
      justify-content: center;
    }
  }

  .settings-sidebar {
    padding: 0;  // Remove padding for better scroll snap
    margin: 0 calc(-1 * var(--spacing-3));  // Extend to viewport edges
    padding: var(--spacing-2) var(--spacing-3);  // Inner padding
  }

  .settings-nav {
    gap: var(--spacing-2);
    scroll-snap-type: x mandatory;  // Enable snap scrolling
    scroll-padding: var(--spacing-3);
  }

  .nav-item {
    min-width: 140px;
    min-height: 44px;  // Touch-friendly
    scroll-snap-align: start;  // Snap to start of item
    padding: var(--spacing-3);
    
    // Enhance visual feedback on mobile
    &.active {
      box-shadow: var(--shadow-md);
      transform: scale(1.02);
    }
  }

  .nav-description {
    display: none;  // Hide descriptions on mobile for cleaner look
  }
  
  .nav-label {
    font-size: var(--text-sm);
    font-weight: 600;
  }

  .setting-item {
    flex-direction: column;
    align-items: stretch;
    gap: var(--spacing-3);
  }

  .select-input,
  .text-input {
    width: 100%;
    min-height: 44px;  // Touch-friendly
    font-size: 16px;  // Prevent iOS zoom
  }

  .about-links {
    flex-direction: column;
    width: 100%;
  }

  .about-link {
    width: 100%;
    justify-content: center;
    padding: var(--spacing-4) var(--spacing-5);
    min-height: 48px;  // Larger touch target
  }
}
</style>
