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
      <div ref="panelRegion" class="settings-content" tabindex="-1">
        <div v-if="activeSectionData?.hasPanel" class="settings-section">
          <BasePanel tone="glass" padding="lg">
            <template #title>{{ activeSectionData.label }}</template>
            <template #description>{{ activeSectionData.panelDescription }}</template>
            <div v-if="!panelHost && !panelHostError" class="panel-load-state" role="status">
              <LoadingSkeleton type="card" />
              <span>Loading {{ activeSectionData.label }} settings…</span>
            </div>
            <div v-else-if="panelHostError" class="panel-load-error" role="alert">
              <p>{{ panelHostError }}</p>
              <button type="button" class="btn btn-primary" @click="loadPanelHost">Retry</button>
            </div>
            <component
              v-else
              :is="panelHost"
              :section="activeSection"
              :panel-props="activePanelProps"
              :panel-listeners="activePanelListeners"
            />
          </BasePanel>
        </div>

        <!-- About Settings -->
        <div v-else-if="activeSection === 'about'" class="settings-section">
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
import { ref, shallowRef, computed, nextTick, onMounted, onBeforeUnmount, watch, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import { useRecordingSettings } from '@/composables/useRecordingSettings'

import { useToast } from '@/composables/useToast'
import { systemApi } from '@/services/api'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import BasePanel from '@/components/base/BasePanel.vue'
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
  hasPanel?: boolean
  panelDescription?: string
}

interface SectionGroup {
  label?: string
  sections: Section[]
}

// No 'overview' pseudo-section: it only mirrored this navigation as a card
// grid, so Settings lands directly in the first real section instead.
const allSectionItems: Section[] = [
  { id: 'twitch', label: 'Twitch Connection', description: 'OAuth & quality settings', icon: 'link', badge: 'Basic', hasPanel: true, panelDescription: 'Connect your Twitch account for enhanced recording quality and features' },
  { id: 'notifications', label: 'Notifications', description: 'Stream alerts & updates', icon: 'bell', badge: 'Basic', hasPanel: true, panelDescription: 'Configure notification preferences for stream events' },
  { id: 'recording', label: 'Recording', description: 'Quality & behavior', icon: 'video', badge: 'Advanced', hasPanel: true, panelDescription: 'Manage recording quality, codecs, and behavior' },
  { id: 'storage', label: 'Storage', description: 'Cleanup & retention', icon: 'server', badge: 'Advanced', hasPanel: true, panelDescription: 'Automatic cleanup policies, retention and storage management' },
  { id: 'favorites', label: 'Favorite Games', description: 'Priority categories', icon: 'star', badge: 'Basic', hasPanel: true, panelDescription: 'Set favorite game categories for priority notifications' },
  { id: 'pwa', label: 'PWA & Mobile', description: 'Mobile app settings', icon: 'smartphone', badge: 'Advanced', hasPanel: true, panelDescription: 'Progressive Web App and mobile-specific settings' },
  { id: 'api-keys', label: 'API Keys', description: 'External access tokens', icon: 'key', badge: 'Safety', hasPanel: true, panelDescription: 'Manage long-lived tokens for external clients (monitoring, scripts, dashboards)' },
  { id: 'proxy', label: 'Proxy Management', description: 'Multi-proxy system', icon: 'server', badge: 'Safety', hasPanel: true, panelDescription: 'Configure multiple proxy servers with automatic health monitoring and failover' },
  { id: 'about', label: 'About', description: 'App information', icon: 'info', badge: 'Account' }
]

const sectionGroups: SectionGroup[] = [
  {
    label: 'Basics',
    sections: allSectionItems.filter(s => s.id === 'twitch' || s.id === 'notifications' || s.id === 'favorites')
  },
  {
    label: 'Advanced',
    sections: allSectionItems.filter(s => s.id === 'recording' || s.id === 'storage' || s.id === 'pwa')
  },
  {
    label: 'Access & Safety',
    sections: allSectionItems.filter(s => s.id === 'api-keys' || s.id === 'proxy' || s.id === 'about')
  }
]

// State
const route = useRoute()
const routeSection = typeof route.query.section === 'string' ? route.query.section : 'twitch'
const activeSection = ref(allSectionItems.some(section => section.id === routeSection) ? routeSection : 'twitch')
const activeSectionData = computed(() => allSectionItems.find(s => s.id === activeSection.value))
const isLoading = ref(true)
const panelHost = shallowRef<Component | null>(null)
const panelHostError = ref('')
const panelRegion = ref<HTMLElement | null>(null)
let panelHostRequest = 0
let acceptsPanelHost = true

async function loadPanelHost() {
  const request = ++panelHostRequest
  panelHostError.value = ''
  try {
    const module = await import('@/components/settings/SettingsPanelHost.vue')
    if (!acceptsPanelHost || request !== panelHostRequest) return
    panelHost.value = module.default
    await nextTick()
    panelRegion.value?.focus()
  } catch {
    if (!acceptsPanelHost || request !== panelHostRequest) return
    panelHostError.value = 'This settings panel could not be loaded.'
  }
}

watch(() => route.query.section, (section) => {
  if (typeof section === 'string' && allSectionItems.some(item => item.id === section)) {
    activeSection.value = section
  }
})

watch(activeSection, async () => {
  if (!panelHost.value) return
  await nextTick()
  panelRegion.value?.focus()
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
  stopRecording
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

const activePanelProps = computed(() => {
  if (activeSection.value === 'notifications') {
    return {
      settings: notificationSettings.value || defaultNotificationSettings,
      streamerSettings: notificationStreamerSettings.value
    }
  }
  if (activeSection.value === 'recording' || activeSection.value === 'storage') {
    return {
      section: activeSection.value,
      settings: recordingSettings.value,
      streamerSettings: recordingStreamerSettings.value,
      activeRecordings: activeRecordings.value
    }
  }
  return {}
})

const activePanelListeners = computed(() => {
  if (activeSection.value === 'notifications') {
    return {
      'update-settings': handleUpdateNotificationSettings,
      'update-streamer-settings': handleUpdateStreamerNotificationSettings
    }
  }
  if (activeSection.value === 'recording' || activeSection.value === 'storage') {
    return {
      update: handleUpdateRecordingSettings,
      'update-streamer': handleUpdateStreamerRecordingSettings,
      'stop-recording': handleStopRecording
    }
  }
  return {}
})

// Initialize
onMounted(() => {
  loadAllSettings()
  loadPanelHost()
})

onBeforeUnmount(() => {
  acceptsPanelHost = false
  panelHostRequest += 1
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
.settings-view {
  // .page-view provides padding/sizing via global styles
  // Page-specific overrides only
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
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-2) var(--spacing-3);
  min-height: 58px;
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
  position: absolute;
  right: var(--spacing-2);
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  stroke: currentColor;
  fill: none;
  flex-shrink: 0;
}

// Settings Content
.settings-content {
  min-width: 0;

  // ------------------------------------------------------------------
  // Cross-panel typography normalization. The panels grew their own
  // heading vocabulary (section-title, status-title, setup-title, ...)
  // at wildly different sizes; this maps them onto one scale so every
  // settings page reads the same:
  //   panel title/desc  -> provided by BasePanel (outside this scope)
  //   group heading     -> text-base semibold
  //   group description -> text-sm secondary
  // ------------------------------------------------------------------
  :deep(h2.section-title),
  :deep(h3.section-title),
  :deep(h3.status-title),
  :deep(h4.setup-title),
  :deep(h5.steps-title),
  :deep(h5.benefits-title) {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    margin: 0 0 var(--spacing-2);
    font-size: var(--text-base);
    font-weight: v.$font-semibold;
    color: var(--text-primary);

    svg,
    .section-icon,
    .title-icon {
      width: 18px;
      height: 18px;
      stroke: var(--primary-color);
      fill: none;
      flex-shrink: 0;
    }
  }

  :deep(p.section-description) {
    margin: 0 0 var(--spacing-4);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.5;
  }

  // Unclassed headings some panels use as group titles (PWA, API keys,
  // recording sub-lists) join the same scale; classed headings like the
  // favorites game-card titles are intentionally excluded.
  :deep(.settings-section h2:not([class])),
  :deep(.settings-section h3:not([class])),
  :deep(.settings-section h4:not([class])) {
    margin: 0 0 var(--spacing-3);
    font-size: var(--text-base);
    font-weight: v.$font-semibold;
    color: var(--text-primary);
  }

  :deep(.settings-section h5:not([class])) {
    margin: 0 0 var(--spacing-2);
    font-size: var(--text-sm);
    font-weight: v.$font-semibold;
    color: var(--text-primary);
  }
}

.settings-section {
  animation: fade-in v.$duration-300 v.$ease-out;
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

  // The page header and the section selector already name the section;
  // repeating it as the panel title cost ~100px of scarce mobile space.
  .settings-content :deep(.base-panel-header) {
    display: none;
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
  color: var(--text-secondary);
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
    color: var(--text-primary);
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
    color: var(--text-primary);
  }
}

.nav-item.active .nav-badge {
  background: var(--background-card);
  color: var(--text-primary) !important;
}

</style>
