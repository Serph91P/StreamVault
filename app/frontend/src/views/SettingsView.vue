<template>
  <div class="page-view settings-view">
    <PageHeader
      title="Settings"
      icon="settings"
      :mobile-title="activeSectionData?.label || 'Settings'"
      :mobile-icon="activeSectionData?.icon || 'settings'"
    />

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <LoadingSkeleton type="card" />
      <LoadingSkeleton type="card" />
      <LoadingSkeleton type="card" />
    </div>

    <!-- Settings Layout -->
    <div v-else class="settings-layout">
      <!-- Mobile Section Selector -->
      <div class="mobile-section-selector">
        <div class="select-wrapper">
          <svg class="select-icon">
            <use href="#icon-menu" />
          </svg>
          <select v-model="activeSection" class="section-select" aria-label="Choose settings section">
            <option
              v-for="section in allSectionItems"
              :key="section.id"
              :value="section.id"
            >
              {{ section.label }}
            </option>
          </select>
        </div>
      </div>

      <!-- Sidebar Navigation (desktop only) -->
      <aside class="settings-sidebar" aria-label="Settings sections">
        <nav class="settings-nav" aria-label="Settings sections">
          <template v-for="group in sectionGroups" :key="group.label || 'overview-group'">
            <div v-if="group.label" class="nav-group-header">{{ group.label }}</div>
            <button
              v-for="section in group.sections"
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
              <span v-if="section.badge" class="nav-badge" :class="`badge-${section.badge.toLowerCase()}`">{{ section.badge }}</span>
              <svg v-if="activeSection === section.id" class="nav-indicator">
                <use href="#icon-chevron-right" />
              </svg>
            </button>
          </template>
        </nav>
      </aside>

      <!-- Settings Content -->
      <div class="settings-content">
        <!-- Overview Section -->
        <div v-if="activeSection === 'overview'" class="settings-section">
          <div class="section-header">
            <h2 class="section-title">
              <svg class="section-icon">
                <use href="#icon-grid" />
              </svg>
              Settings Overview
            </h2>
            <p class="section-description">
              Quick status summary for all settings areas
            </p>
          </div>

          <div class="overview-grid">
            <button @click="activeSection = 'twitch'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-link" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">Twitch Connection</span>
                <span class="overview-card-desc">OAuth tokens & connection status</span>
              </div>
              <span class="overview-badge badge-basic">Basic</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>

            <button @click="activeSection = 'notifications'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-bell" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">Notifications</span>
                <span class="overview-card-desc">{{ notificationSettings?.notifications_enabled ? 'Enabled' : 'Disabled' }} &bull; {{ notificationStreamerSettings.length }} streamers</span>
              </div>
              <span class="overview-badge badge-basic">Basic</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>

            <button @click="activeSection = 'recording'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-video" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">Recording</span>
                <span class="overview-card-desc">{{ recordingSettings?.enabled ? 'Enabled' : 'Disabled' }} &bull; {{ activeRecordings.length }} active</span>
              </div>
              <span class="overview-badge badge-advanced">Advanced</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>

            <button @click="activeSection = 'favorites'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-star" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">Favorite Games</span>
                <span class="overview-card-desc">Priority game categories</span>
              </div>
              <span class="overview-badge badge-basic">Basic</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>

            <button @click="activeSection = 'pwa'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-smartphone" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">PWA & Mobile</span>
                <span class="overview-card-desc">App install & push notifications</span>
              </div>
              <span class="overview-badge badge-advanced">Advanced</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>

            <button @click="activeSection = 'api-keys'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-key" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">API Keys</span>
                <span class="overview-card-desc">External access tokens</span>
              </div>
              <span class="overview-badge badge-safety">Safety</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>

            <button @click="activeSection = 'proxy'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-server" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">Proxy Management</span>
                <span class="overview-card-desc">Multi-proxy system & failover</span>
              </div>
              <span class="overview-badge badge-safety">Safety</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>

            <button @click="activeSection = 'about'" class="overview-card">
              <div class="overview-card-icon">
                <svg><use href="#icon-info" /></svg>
              </div>
              <div class="overview-card-body">
                <span class="overview-card-label">About</span>
                <span class="overview-card-desc">{{ displayVersion }}</span>
              </div>
              <span class="overview-badge badge-account">Account</span>
              <svg class="overview-arrow"><use href="#icon-chevron-right" /></svg>
            </button>
          </div>
        </div>

        <!-- Twitch Connection Settings -->
        <div v-if="activeSection === 'twitch'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>Twitch Connection</template>
            <template #description>Connect your Twitch account for enhanced recording quality and features</template>
            <TwitchConnectionPanel />
          </BasePanel>
        </div>

        <!-- Notifications Settings -->
        <div v-if="activeSection === 'notifications'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>Notifications</template>
            <template #description>Configure notification preferences for stream events</template>
            <NotificationSettingsPanel
              :settings="notificationSettings || defaultNotificationSettings"
              :streamer-settings="notificationStreamerSettings"
              @update-settings="handleUpdateNotificationSettings"
              @update-streamer-settings="handleUpdateStreamerNotificationSettings"
            />
          </BasePanel>
        </div>

        <!-- Recording Settings -->
        <div v-if="activeSection === 'recording'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>Recording</template>
            <template #description>Manage recording quality, storage, and behavior</template>
            <RecordingSettingsPanel
              :settings="recordingSettings"
              :streamer-settings="recordingStreamerSettings"
              :active-recordings="activeRecordings"
              @update="handleUpdateRecordingSettings"
              @update-streamer="handleUpdateStreamerRecordingSettings"
              @stop-recording="handleStopRecording"
            />
          </BasePanel>
        </div>

        <!-- Proxy Management -->
        <div v-if="activeSection === 'proxy'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>Proxy Management</template>
            <template #description>Configure multiple proxy servers with automatic health monitoring and failover</template>
            <ProxySettingsPanel />
          </BasePanel>
        </div>

        <!-- Favorites Settings -->
        <div v-if="activeSection === 'favorites'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>Favorite Games</template>
            <template #description>Set favorite game categories for priority notifications</template>
            <FavoritesSettingsPanel />
          </BasePanel>
        </div>

        <!-- PWA Settings -->
        <div v-if="activeSection === 'pwa'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>PWA & Mobile</template>
            <template #description>Progressive Web App and mobile-specific settings</template>
            <PWAPanel />
          </BasePanel>
        </div>

        <!-- API Keys -->
        <div v-if="activeSection === 'api-keys'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>API Keys</template>
            <template #description>Manage long-lived tokens for external clients (monitoring, scripts, dashboards)</template>
            <ApiKeysPanel />
          </BasePanel>
        </div>

        <!-- About Settings -->
        <div v-if="activeSection === 'about'" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>About</template>
            <template #description>Application information and version details</template>
            <div class="about-content">
              <div class="about-logo">
                <svg class="logo-icon">
                  <use href="#icon-video" />
                </svg>
              </div>
              <h3 class="about-title">StreamVault</h3>

              <!-- Version Info -->
              <div v-if="versionInfo" class="version-info">
                <p class="about-version">
                  {{ displayVersion }}
                  <span v-if="versionInfo.branch && versionInfo.branch !== 'unknown'" class="version-branch">{{ versionInfo.branch }}</span>
                </p>
                <p v-if="versionInfo.commit_sha && versionInfo.commit_sha !== 'unknown'" class="build-date">
                  Commit: <code>{{ versionInfo.commit_sha.substring(0, 7) }}</code>
                </p>
                <p v-if="versionInfo.build_date" class="build-date">
                  Built: {{ formatBuildDate(versionInfo.build_date) }}
                </p>

                <!-- Update Check -->
                <div v-if="versionInfo.update_available" class="update-notice">
                  <span class="update-icon">🎉</span>
                  <span class="update-text">
                    Update available:
                    <strong>{{ displayVersion }}</strong>
                    &rarr;
                    <strong>{{ versionInfo.latest_version }}</strong>
                    <span v-if="versionInfo.release_channel" class="channel-badge">
                      {{ versionInfo.release_channel }}
                    </span>
                  </span>
                  <a v-if="versionInfo.latest_version_url"
                     :href="versionInfo.latest_version_url"
                     target="_blank"
                     class="btn btn-sm btn-primary">
                    View Release
                  </a>
                </div>
                <div v-else-if="versionInfo.update_check_error" class="update-notice update-error">
                  <span class="update-icon">⚠️</span>
                  <span class="update-text">
                    Update check failed: {{ versionInfo.update_check_error }}
                  </span>
                </div>
                <div v-else class="up-to-date">
                  <span>{{ upToDateText }}</span>
                  <a v-if="versionInfo.latest_version_url"
                     :href="versionInfo.latest_version_url"
                     target="_blank"
                     class="release-link">
                    View release
                  </a>
                </div>
              </div>
              <p v-else class="about-version">Loading version...</p>

              <p class="about-description">
                Automated stream recording and management system for Twitch content creators.
              </p>
              <div class="about-links">
                <a href="https://github.com/Serph91P/StreamVault" target="_blank" class="about-link">
                  <svg class="icon">
                    <use href="#icon-home" />
                  </svg>
                  GitHub
                </a>
                <a href="https://github.com/Serph91P/StreamVault/releases" target="_blank" class="about-link">
                  <svg class="icon">
                    <use href="#icon-download" />
                  </svg>
                  Releases
                </a>
              </div>
            </div>
          </BasePanel>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useTheme } from '@/composables/useTheme'
import { useToast } from '@/composables/useToast'
import { systemApi } from '@/services/api'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import BasePanel from '@/components/base/BasePanel.vue'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import ProxySettingsPanel from '@/components/settings/ProxySettingsPanel.vue'
import FavoritesSettingsPanel from '@/components/settings/FavoritesSettingsPanel.vue'
import PWAPanel from '@/components/settings/PWAPanel.vue'
import TwitchConnectionPanel from '@/components/settings/TwitchConnectionPanel.vue'
import ApiKeysPanel from '@/components/settings/ApiKeysPanel.vue'
import PageHeader from '@/components/base/PageHeader.vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'
import type { RecordingSettings } from '@/types/recording'

// Section metadata for nav badges
type SectionBadge = 'Basic' | 'Advanced' | 'Account' | 'Safety' | 'Danger'

interface Section {
  id: string
  label: string
  description: string
  icon: string
  badge?: SectionBadge
}

interface SectionGroup {
  label?: string
  sections: Section[]
}

const allSectionItems: Section[] = [
  { id: 'overview', label: 'Overview', description: 'Settings at a glance', icon: 'grid' },
  { id: 'twitch', label: 'Twitch Connection', description: 'OAuth & quality settings', icon: 'link', badge: 'Basic' },
  { id: 'notifications', label: 'Notifications', description: 'Stream alerts & updates', icon: 'bell', badge: 'Basic' },
  { id: 'recording', label: 'Recording', description: 'Quality & storage', icon: 'video', badge: 'Advanced' },
  { id: 'favorites', label: 'Favorite Games', description: 'Priority categories', icon: 'star', badge: 'Basic' },
  { id: 'pwa', label: 'PWA & Mobile', description: 'Mobile app settings', icon: 'smartphone', badge: 'Advanced' },
  { id: 'api-keys', label: 'API Keys', description: 'External access tokens', icon: 'key', badge: 'Safety' },
  { id: 'proxy', label: 'Proxy Management', description: 'Multi-proxy system', icon: 'server', badge: 'Safety' },
  { id: 'about', label: 'About', description: 'App information', icon: 'info', badge: 'Account' }
]

const sectionGroups: SectionGroup[] = [
  {
    sections: [allSectionItems[0]]
  },
  {
    label: 'Basics',
    sections: allSectionItems.filter(s => s.id === 'twitch' || s.id === 'notifications' || s.id === 'favorites')
  },
  {
    label: 'Advanced',
    sections: allSectionItems.filter(s => s.id === 'recording' || s.id === 'pwa')
  },
  {
    label: 'Access & Safety',
    sections: allSectionItems.filter(s => s.id === 'api-keys' || s.id === 'proxy' || s.id === 'about')
  }
]

// State
const route = useRoute()
const routeSection = typeof route.query.section === 'string' ? route.query.section : 'overview'
const activeSection = ref(allSectionItems.some(section => section.id === routeSection) ? routeSection : 'overview')
const activeSectionData = computed(() => allSectionItems.find(s => s.id === activeSection.value))
const isLoading = ref(true)

watch(() => route.query.section, (section) => {
  if (typeof section === 'string' && allSectionItems.some(item => item.id === section)) {
    activeSection.value = section
  }
})

// Version information
const versionInfo = ref<any>(null)

// Display fallback: version → 'dev-<sha7>' → 'dev'
const displayVersion = computed(() => {
  const v = versionInfo.value
  if (!v) return 'dev'
  if (v.version && v.version !== 'unknown' && v.version !== 'dev') return v.version
  if (v.commit_sha && v.commit_sha !== 'unknown') return `dev-${v.commit_sha.substring(0, 7)}`
  return 'dev'
})

const upToDateText = computed(() => {
  const v = versionInfo.value
  if (!v) return "You're running the latest version"
  const channel = v.release_channel === 'prerelease' ? 'develop' : 'stable'
  if (v.latest_version) {
    return `You're on the latest ${channel} release (${v.latest_version})`
  }
  return `You're on the latest ${channel} release`
})

// Theme management - use global theme composable
const { theme, setTheme } = useTheme()

// Toast notifications
const toast = useToast()

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
  cleanupOldRecordings: _cleanupOldRecordings
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

    // Load version information
    await loadVersionInfo()
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    isLoading.value = false
  }
}

// Load version information
async function loadVersionInfo() {
  try {
    versionInfo.value = await systemApi.getVersion()
  } catch (error) {
    console.error('Failed to load version info:', error)
  }
}

// Format build date
function formatBuildDate(isoDate: string): string {
  try {
    const date = new Date(isoDate)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return isoDate
  }
}

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
    toast.success('Notification settings saved successfully')
  } catch (error) {
    console.error('Failed to update notification settings:', error)
    toast.error('Failed to save notification settings')
  }
}

async function handleUpdateStreamerNotificationSettings(
  streamerId: number,
  settings: Partial<StreamerNotificationSettings>
) {
  try {
    await updateStreamerNotificationSettings(streamerId, settings)
    notificationStreamerSettings.value = await getNotificationStreamerSettings()
    toast.success('Streamer notification settings saved successfully')
  } catch (error) {
    console.error('Failed to update streamer notification settings:', error)
    toast.error('Failed to save streamer notification settings')
  }
}

// Recording handlers
async function handleUpdateRecordingSettings(newSettings: RecordingSettings) {
  try {
    await updateRecordingSettings(newSettings)
    toast.success('Recording settings saved successfully')
  } catch (error) {
    console.error('Failed to update recording settings:', error)
    toast.error('Failed to save recording settings')
  }
}

async function handleUpdateStreamerRecordingSettings(streamerId: number, settings: any) {
  try {
    await updateStreamerRecordingSettings(streamerId, settings)
    await fetchRecordingStreamerSettings()
    toast.success('Streamer recording settings saved successfully')
  } catch (error) {
    console.error('Failed to update streamer recording settings:', error)
    toast.error('Failed to save streamer recording settings')
  }
}

async function handleStopRecording(recordingId: number) {
  try {
    await stopRecording(recordingId)
    await fetchActiveRecordings()
    toast.success('Recording stopped successfully')
  } catch (error) {
    console.error('Failed to stop recording:', error)
    toast.error('Failed to stop recording')
  }
}

// Initialize
onMounted(() => {
  loadAllSettings()
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
.settings-view {
  // .page-view provides padding/sizing via global styles
  // Page-specific overrides only
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  min-height: 44px;
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

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
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
  min-height: 44px;
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
    background: v.$primary-700;
    color: white;

    .nav-icon {
      stroke: white;
    }

    .nav-description {
      color: rgba(255, 255, 255, 0.92);
    }

    .nav-indicator {
      stroke: white;
    }
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
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
  color: var(--text-secondary);
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

// Settings Cards - NO background, uses GlassCard component for glassmorphism
.settings-card {
  // NO background - GlassCard handles this
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  overflow: hidden;
  margin-bottom: var(--spacing-5);

  // Reduce margins on mobile
  @include m.respond-below('sm') {
    margin-bottom: var(--spacing-3);
    border-radius: var(--radius-lg);
  }
}

.card-content {
  padding: var(--spacing-6);

  // Mobile: Reduce padding for better content visibility
  @include m.respond-below('sm') {
    padding: var(--spacing-3);
  }
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
  margin: 0 0 var(--spacing-2) 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
}

.version-branch {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: v.$font-medium;
  background: var(--primary-color);
  color: white;
}

.build-date {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin: 0 0 var(--spacing-3) 0;
}

.update-notice {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  background: rgba(var(--success-color-rgb), 0.1);
  border: 1px solid var(--success-color);
  border-radius: var(--radius-md);
  margin: var(--spacing-3) 0;

  .update-icon {
    font-size: var(--text-2xl);
  }

  .update-text {
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
}

.up-to-date {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2);
  font-size: var(--text-sm);
  color: var(--success-color);
  margin: var(--spacing-3) 0;
  flex-wrap: wrap;

  .release-link {
    color: var(--text-secondary);
    text-decoration: underline;
    font-size: var(--text-xs);

    &:hover {
      color: var(--text-primary);
    }
  }
}

.update-error {
  color: var(--warning-color);
}

.channel-badge {
  display: inline-block;
  margin-left: var(--spacing-2);
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--surface-secondary, rgba(255, 255, 255, 0.08));
  color: var(--text-secondary);
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.5px;
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
  box-shadow: var(--glass-shadow-sm);
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
    box-shadow: var(--glass-shadow-md);
  }

  &:active {
    transform: translateY(0);
  }
}

// Mobile section selector - hidden on desktop
.mobile-section-selector {
  display: none;
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

@include m.respond-below('lg') {  // < 1024px
  .settings-layout {
    grid-template-columns: 1fr;
  }

  // Hide desktop sidebar, show mobile selector
  .settings-sidebar {
    display: none;
  }

  .mobile-section-selector {
    display: block;
    margin-bottom: var(--spacing-4);
  }

  .section-select {
    width: 100%;
    padding: var(--spacing-3) var(--spacing-4);
    padding-left: var(--spacing-10);
    background: var(--background-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    color: var(--text-primary);
    font-size: var(--text-base);
    font-weight: v.$font-medium;
    appearance: none;
    cursor: pointer;
    min-height: 48px;

    &:focus {
      outline: 2px solid var(--primary-color);
      outline-offset: -2px;
    }
  }

  .mobile-section-selector .select-wrapper {
    position: relative;

    .select-icon {
      position: absolute;
      left: var(--spacing-3);
      top: 50%;
      transform: translateY(-50%);
      width: 20px;
      height: 20px;
      stroke: var(--text-secondary);
      fill: none;
      pointer-events: none;
      z-index: 1;
    }
  }

  // Override PageHeader title visibility at settings breakpoint
  :deep(.page-header .desktop-title) {
    display: none;
  }

  :deep(.page-header .mobile-title) {
    display: flex;
  }

  // Hide section header on mobile (already shown in mobile page title)
  .section-header {
    display: none;
  }

  .nav-indicator {
    display: none;
  }

  // Ensure content is not hidden behind fixed BottomNav (64px + safe area)
  .settings-content {
    padding-bottom: calc(64px + env(safe-area-inset-bottom, 0px) + v.$spacing-6);
  }
}

@include m.respond-below('sm') {  // < 640px
  .settings-view {
    padding: var(--spacing-4) var(--spacing-3);
  }

  .btn-action {
    width: 100%;
    min-height: 44px;  // Touch-friendly
    justify-content: center;
  }

  // Reduce card-content padding on mobile for better content visibility
  .card-content {
    padding: var(--spacing-3);
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

// Nav group headers
.nav-group-header {
  font-size: var(--text-xs);
  font-weight: v.$font-semibold;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: var(--spacing-3) var(--spacing-3) var(--spacing-1);
  margin-top: var(--spacing-2);
  border-bottom: 1px solid var(--border-color);
}

.nav-group-header:first-of-type {
  margin-top: 0;
}

// Nav badges
.nav-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  font-size: 0.625rem;
  font-weight: v.$font-semibold;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  margin-right: var(--spacing-2);

  &.badge-basic {
    background: rgba(var(--primary-500-rgb), 0.15);
    color: var(--text-primary);
  }

  &.badge-advanced {
    background: rgba(var(--accent-500-rgb), 0.15);
    color: var(--accent-color);
  }

  &.badge-safety {
    background: rgba(var(--warning-500-rgb), 0.15);
    color: var(--text-primary);
  }

  &.badge-account {
    background: rgba(var(--info-500-rgb), 0.15);
    color: var(--text-primary);
  }

  &.badge-danger {
    background: rgba(var(--danger-500-rgb), 0.15);
    color: var(--danger-color);
  }
}

// Overview grid
.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-3);
}

.overview-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  text-align: left;
  color: inherit;
  font: inherit;
  min-height: 56px;

  &:hover {
    border-color: var(--primary-color);
    background: rgba(var(--primary-500-rgb), 0.04);
    transform: translateY(-1px);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.overview-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: rgba(var(--primary-500-rgb), 0.1);
  flex-shrink: 0;

  svg {
    width: 20px;
    height: 20px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.overview-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.overview-card-label {
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  line-height: 1.3;
}

.overview-card-desc {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  font-size: 0.625rem;
  font-weight: v.$font-semibold;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  margin-left: auto;

  &.badge-basic {
    background: rgba(var(--primary-500-rgb), 0.12);
    color: var(--text-primary);
  }

  &.badge-advanced {
    background: rgba(var(--accent-500-rgb), 0.12);
    color: var(--accent-color);
  }

  &.badge-safety {
    background: rgba(var(--warning-500-rgb), 0.12);
    color: var(--warning-color-dark);
  }

  &.badge-account {
    background: rgba(var(--info-500-rgb), 0.12);
    color: var(--info-color);
  }
}

.overview-arrow {
  width: 16px;
  height: 16px;
  stroke: var(--text-tertiary);
  fill: none;
  flex-shrink: 0;
}

@include m.respond-below('md') {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
