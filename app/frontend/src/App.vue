<template>
  <IconSprite />

  <div class="app">
    <AppShell :show-shell="!isAuthPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in" @before-enter="scrollToTop">
          <component :is="Component" />
        </transition>
      </router-view>
    </AppShell>

    <!-- Toast Notification System (CRITICAL: Always visible) -->
    <ToastContainer />
    
    <!-- PWA Install Prompt -->
    <PWAInstallPrompt />
  </div>
</template>

<script setup>
import IconSprite from '@/components/icons/IconSprite.vue'
import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import AppShell from '@/components/AppShell.vue'
import '@/styles/main.scss'
import { onMounted, onUnmounted, watch, provide, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useSystemAndRecordingStatus } from '@/composables/useSystemAndRecordingStatus'
import { useTheme } from '@/composables/useTheme'
import { useToast } from '@/composables/useToast'
import { useNotificationStore } from '@/stores/notifications'
import { useRealtimeStore } from '@/stores/realtime'
import { hasRealtimeEventType, toCanonicalNotificationEvent } from '@/types/events'

// Initialize theme
const { initializeTheme } = useTheme()
initializeTheme()

// Initialize toast system (centralized - handles all toast notifications via useToast)
const toast = useToast()

// Check if current route is an auth page
const route = useRoute()

// Scroll to top on every route change (belt-and-suspenders with router.afterEach)
watch(() => route.fullPath, () => {
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
})

const isAuthPage = computed(() => {
  const authPaths = ['/auth/login', '/auth/setup', '/welcome', '/onboarding']
  return authPaths.includes(route.path)
})

// Provide hybrid status globally
const hybridStatus = useSystemAndRecordingStatus()
provide('hybridStatus', hybridStatus)

// Initialize hybrid status system
onMounted(() => {
  // Start the hybrid status system
  hybridStatus.fetchAllStatus()
})

const notificationStore = useNotificationStore()

const realtime = useRealtimeStore()

// Scroll to top on page transitions (for out-in mode)
function scrollToTop() {
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
}

// Process toast notifications from WebSocket - uses unified useToast system
function processToastNotification(message) {
  if (hasRealtimeEventType(message, 'toast_notification')) {
    const { 
      toast_type = 'info',    // Backend sends "toast_type", not "type"
      title = '',
      message: toastMessage, 
      duration = 5000
    } = message.data || {}
    
    // Combine title and message for display
    const displayMessage = title ? `${title}: ${toastMessage}` : toastMessage
    
    if (displayMessage) {
      // Use unified toast system
      toast.show(displayMessage, toast_type, duration)
    }
  }
  
  // CRITICAL: Listen for recording_failed WebSocket events
  if (hasRealtimeEventType(message, 'recording_failed')) {
    const streamer_name = message.data?.streamer_name || 'Unknown'
    const error_message = message.data?.error_message || 'Unknown error'
    
    toast.error(`Recording failed: ${streamer_name} - ${error_message}`, 5000)
    
    console.error('🚨 Recording failed:', {
      streamer: streamer_name,
      error: error_message,
      data: message.data
    })
  }
}

// Auth state is hydrated by router.beforeEach (which calls /auth/setup +
// /auth/check on every navigation, including the initial one). Calling
// checkStoredAuth() here a second time produced a visible "reload" effect:
// the page rendered after the router-guard, then this onMounted hook fired
// another /auth/check which could race and trigger its own router.push.
// Keep the import for explicit logout flows; remove the duplicate boot call.

const addNotificationFromRealtime = (message) => {
  const notificationEvent = toCanonicalNotificationEvent(message)
  if (notificationEvent) {
    notificationStore.addFromEvent(notificationEvent)
  }
}

const notificationRealtimeTypes = [
  'stream.online',
  'stream.offline',
  'channel.update',
  'stream.update',
  'recording.started',
  'recording.completed',
  'recording.failed',
  'recording.finished',
  'recording.available',
  'stream_online',
  'stream_offline',
  'recording_started',
  'recording_completed',
  'recording_failed',
  'recording_finished',
  'recording_available',
  'notification_event',
  'test'
]

const appRealtimeUnsubs = []

onMounted(() => {
  appRealtimeUnsubs.push(
    realtime.onEvent('toast_notification', processToastNotification),
    realtime.onEvent('recording_failed', processToastNotification),
    realtime.onEvents(notificationRealtimeTypes, addNotificationFromRealtime)
  )
})

onUnmounted(() => {
  appRealtimeUnsubs.forEach((fn) => fn())
})

// Load notification state from backend on mount
onMounted(async () => {
  notificationStore.load()
  await notificationStore.syncBackendState()
  
  realtime.recentEvents.forEach(addNotificationFromRealtime)
})
</script>

<style lang="scss">
@use '@/styles/variables' as v;

// Page transitions
.page-enter-active,
.page-leave-active {
  transition: opacity v.$duration-200 v.$ease-out;
}
.page-enter-from,
.page-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active {
    transition: none;
  }
}
</style>
