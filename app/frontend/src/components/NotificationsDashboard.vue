<template>
  <div class="notifications-dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <h2>Notifications & Events</h2>
      <div class="header-actions">
        <div class="notification-status" :class="{ 'enabled': notificationSystem?.enabled }">
          <div class="status-indicator">
            <div class="status-dot" :class="{ 'active': notificationSystem?.enabled }"></div>
            <span>{{ notificationSystem?.enabled ? 'Enabled' : 'Disabled' }}</span>
          </div>
        </div>
        <button 
          class="refresh-btn"
          @click="refreshNotifications"
          :disabled="isLoading"
        >
          <RefreshIcon :spinning="isLoading" />
          Refresh
        </button>
      </div>
    </div>

    <!-- System Status Cards -->
    <div class="status-cards">
      <!-- Notification System Status -->
      <div class="status-card">
        <div class="card-header">
          <NotificationIcon />
          <h3>Notification System</h3>
        </div>
        <div class="card-content">
          <div class="status-grid">
            <div class="status-item">
              <span class="label">Status:</span>
              <span class="value" :class="{ 'enabled': notificationSystem?.enabled }">
                {{ notificationSystem?.enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </div>
            <div class="status-item">
              <span class="label">Webhook URL:</span>
              <span class="value" :class="{ 'configured': notificationSystem?.url_configured }">
                {{ notificationSystem?.url_configured ? 'Configured' : 'Not Set' }}
              </span>
            </div>
            <div class="status-item">
              <span class="label">Active Subscriptions:</span>
              <span class="value">{{ notificationSystem?.active_subscriptions || 0 }}</span>
            </div>
            <div class="status-item">
              <span class="label">Configured Streamers:</span>
              <span class="value">{{ notificationSystem?.streamers_with_notifications || 0 }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Push Notifications Status -->
      <div class="status-card">
        <div class="card-header">
          <PushIcon />
          <h3>Push Notifications</h3>
        </div>
        <div class="card-content">
          <div class="push-stats">
            <div class="stat">
              <div class="stat-number">{{ notificationSystem?.active_subscriptions || 0 }}</div>
              <div class="stat-label">Active Subscriptions</div>
            </div>
          </div>
          <div class="push-actions">
            <button class="action-btn" @click="testPushNotification">
              Test Push Notification
            </button>
            <button class="action-btn" @click="manageSubscriptions">
              Manage Subscriptions
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Events -->
    <div class="events-section">
      <div class="section-header">
        <h3>Recent Events</h3>
        <div class="event-filters">
          <select v-model="eventTypeFilter">
            <option value="all">All Events</option>
            <option value="stream_online">Stream Online</option>
            <option value="stream_offline">Stream Offline</option>
            <option value="recording_started">Recording Started</option>
            <option value="recording_stopped">Recording Stopped</option>
            <option value="system">System Events</option>
          </select>
          <button class="clear-btn" @click="clearEvents" title="Clear event history">
            <ClearIcon />
          </button>
        </div>
      </div>

      <!-- Events List -->
      <div class="events-list" v-if="filteredEvents.length > 0">
        <div 
          v-for="event in filteredEvents"
          :key="event.id || event.timestamp"
          class="event-item"
          :class="`event-${event.type}`"
        >
          <div class="event-icon">
            <component :is="getEventIcon(event.type)" />
          </div>
          <div class="event-content">
            <div class="event-message">{{ event.message }}</div>
            <div class="event-details">
              <span class="event-streamer" v-if="event.streamer_name">
                {{ event.streamer_name }}
              </span>
              <span class="event-time">{{ formatEventTime(event.timestamp) }}</span>
            </div>
          </div>
          <div class="event-type">{{ formatEventType(event.type) }}</div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="!isLoading" class="empty-events">
        <div class="empty-icon">📢</div>
        <h4>No recent events</h4>
        <p>{{ getEmptyEventsMessage() }}</p>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading" class="loading-events">
        <div class="spinner"></div>
        <p>Loading events...</p>
      </div>
    </div>

    <!-- Settings Quick Actions -->
    <div class="quick-actions">
      <button class="action-btn primary" @click="openNotificationSettings">
        <SettingsIcon />
        Notification Settings
      </button>
      <button class="action-btn" @click="openStreamerSettings">
        <StreamerIcon />
        Streamer Notifications
      </button>
      <button class="action-btn" @click="viewEventHistory">
        <HistoryIcon />
        Full Event History
      </button>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="error-banner">
      <AlertIcon />
      <span>{{ error }}</span>
      <button @click="clearError" class="close-btn">×</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useHybridStatus } from '@/composables/useHybridStatus'

// Icons
const RefreshIcon = { 
  template: '<div class="icon refresh-icon" :class="{ spinning: spinning }">↻</div>',
  props: ['spinning']
}
const AlertIcon = { template: '<div class="icon alert-icon">⚠</div>' }
const NotificationIcon = { template: '<div class="icon notification-icon">🔔</div>' }
const PushIcon = { template: '<div class="icon push-icon">📱</div>' }
const ClearIcon = { template: '<div class="icon clear-icon">🗑</div>' }
const SettingsIcon = { template: '<div class="icon settings-icon">⚙️</div>' }
const StreamerIcon = { template: '<div class="icon streamer-icon">👤</div>' }
const HistoryIcon = { template: '<div class="icon history-icon">📜</div>' }

// Event type icons
const StreamOnlineIcon = { template: '<div class="icon stream-online">🟢</div>' }
const StreamOfflineIcon = { template: '<div class="icon stream-offline">🔴</div>' }
const RecordingStartedIcon = { template: '<div class="icon recording-started">🎬</div>' }
const RecordingStoppedIcon = { template: '<div class="icon recording-stopped">⏹️</div>' }
const SystemIcon = { template: '<div class="icon system">⚙️</div>' }
const DefaultIcon = { template: '<div class="icon default">📝</div>' }

// Hybrid status composable
const {
  notificationsStatus,
  isLoading,
  error,
  fetchNotificationsStatus
} = useHybridStatus()

// Local state
const eventTypeFilter = ref('all')
const localError = ref<string | null>(null)

// Computed
const notificationSystem = computed(() => 
  notificationsStatus.value?.notification_system || null
)

const recentEvents = computed(() => 
  notificationsStatus.value?.recent_events || []
)

const filteredEvents = computed(() => {
  if (eventTypeFilter.value === 'all') {
    return recentEvents.value
  }
  
  return recentEvents.value.filter(event => 
    event.type === eventTypeFilter.value
  )
})

const displayError = computed(() => error.value || localError.value)

// Methods
const refreshNotifications = async () => {
  try {
    await fetchNotificationsStatus(false)
    localError.value = null
  } catch (err) {
    localError.value = 'Failed to refresh notifications'
  }
}

const clearError = () => {
  localError.value = null
}

const getEventIcon = (eventType: string) => {
  switch (eventType) {
    case 'stream_online': 
    case 'streamer_online': 
      return StreamOnlineIcon
    case 'stream_offline': 
    case 'streamer_offline': 
      return StreamOfflineIcon
    case 'recording_started': 
      return RecordingStartedIcon
    case 'recording_stopped': 
    case 'recording_completed': 
      return RecordingStoppedIcon
    case 'system': 
      return SystemIcon
    default: 
      return DefaultIcon
  }
}

const formatEventType = (eventType: string): string => {
  const typeMap: Record<string, string> = {
    'stream_online': 'Stream Online',
    'stream_offline': 'Stream Offline',
    'streamer_online': 'Streamer Online',
    'streamer_offline': 'Streamer Offline',
    'recording_started': 'Recording Started',
    'recording_stopped': 'Recording Stopped',
    'recording_completed': 'Recording Completed',
    'system': 'System Event',
    'notification_sent': 'Notification Sent',
    'webhook_failed': 'Webhook Failed'
  }
  
  return typeMap[eventType] || eventType.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatEventTime = (timestamp: string): string => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMinutes = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)
  
  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString()
}

const getEmptyEventsMessage = (): string => {
  if (eventTypeFilter.value !== 'all') {
    return `No ${formatEventType(eventTypeFilter.value).toLowerCase()} events found`
  }
  return 'No recent events to display'
}

const testPushNotification = async () => {
  try {
    // TODO: Implement test push notification API
    console.log('Testing push notification...')
    localError.value = null
  } catch (err) {
    localError.value = 'Failed to send test notification'
  }
}

const manageSubscriptions = () => {
  // TODO: Navigate to push subscription management
  console.log('Managing subscriptions...')
}

const clearEvents = async () => {
  try {
    // TODO: Implement clear events API
    console.log('Clearing event history...')
  } catch (err) {
    localError.value = 'Failed to clear events'
  }
}

const openNotificationSettings = () => {
  // TODO: Navigate to notification settings
  console.log('Opening notification settings...')
}

const openStreamerSettings = () => {
  // TODO: Navigate to streamer notification settings
  console.log('Opening streamer settings...')
}

const viewEventHistory = () => {
  // TODO: Navigate to full event history
  console.log('Viewing event history...')
}
</script>

<style scoped>
.notifications-dashboard {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e2e8f0;
}

.dashboard-header h2 {
  margin: 0;
  color: #1a202c;
  font-size: 1.75rem;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.notification-status {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  background: #fee2e2;
  color: #991b1b;
}

.notification-status.enabled {
  background: #dcfce7;
  color: #166534;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
}

.status-dot.active {
  background: #22c55e;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background: white;
  color: #374151;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: #f9fafb;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.status-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.status-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #f1f5f9;
}

.card-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #1e293b;
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
}

.status-item .label {
  color: #64748b;
  font-weight: 500;
}

.status-item .value {
  color: #1e293b;
  font-weight: 500;
}

.status-item .value.enabled,
.status-item .value.configured {
  color: #059669;
}

.push-stats {
  text-align: center;
  margin-bottom: 1rem;
}

.stat-number {
  font-size: 2rem;
  font-weight: 700;
  color: #1e293b;
}

.stat-label {
  color: #64748b;
  font-size: 0.875rem;
}

.push-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.events-section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #f1f5f9;
}

.section-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #1e293b;
}

.event-filters {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.event-filters select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background: white;
}

.clear-btn {
  padding: 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: #fee2e2;
  border-color: #ef4444;
}

.events-list {
  max-height: 400px;
  overflow-y: auto;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  margin-bottom: 0.5rem;
  background: #f8fafc;
  border-radius: 0.375rem;
  border-left: 3px solid #e2e8f0;
}

.event-item.event-stream_online,
.event-item.event-streamer_online {
  border-left-color: #22c55e;
}

.event-item.event-recording_started {
  border-left-color: #ef4444;
}

.event-item.event-stream_offline,
.event-item.event-streamer_offline,
.event-item.event-recording_stopped {
  border-left-color: #6b7280;
}

.event-icon {
  flex-shrink: 0;
  font-size: 1.25rem;
}

.event-content {
  flex: 1;
}

.event-message {
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 0.25rem;
}

.event-details {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
  color: #64748b;
}

.event-streamer {
  font-weight: 500;
}

.event-type {
  flex-shrink: 0;
  padding: 0.25rem 0.5rem;
  background: #e2e8f0;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #64748b;
}

.empty-events, .loading-events {
  text-align: center;
  padding: 3rem 2rem;
  color: #6b7280;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.empty-events h4 {
  margin: 0 0 0.5rem 0;
  color: #374151;
}

.spinner {
  width: 2rem;
  height: 2rem;
  border: 2px solid #e5e7eb;
  border-top: 2px solid #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

.quick-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background: white;
  color: #374151;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #f9fafb;
}

.action-btn.primary {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.action-btn.primary:hover {
  background: #2563eb;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  margin-top: 1rem;
  background: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 0.375rem;
  color: #991b1b;
}

.close-btn {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  color: #991b1b;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Responsive */
@media (max-width: 768px) {
  .notifications-dashboard {
    padding: 1rem;
  }
  
  .dashboard-header {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }
  
  .header-actions {
    justify-content: center;
  }
  
  .status-cards {
    grid-template-columns: 1fr;
  }
  
  .section-header {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }
  
  .event-filters {
    justify-content: center;
  }
  
  .quick-actions {
    flex-direction: column;
  }
  
  .push-actions {
    flex-direction: column;
  }
}
</style>
