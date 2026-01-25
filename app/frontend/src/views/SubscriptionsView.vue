<template>
  <div class="page-view subscriptions-view">
    <!-- Header -->
    <div class="view-header">
      <div class="header-content">
        <h1 class="page-title">
          <svg class="icon-title">
            <use href="#icon-rss" />
          </svg>
          Subscription Management
        </h1>
        <p class="page-subtitle">
          Manage your Twitch EventSub subscriptions for tracked streamers
        </p>
      </div>

      <div class="header-actions">
        <button @click="loadSubscriptions" :disabled="loading" class="btn-action btn-secondary" v-ripple>
          <svg class="icon">
            <use href="#icon-refresh-cw" />
          </svg>
          <span>{{ loading ? 'Loading...' : 'Refresh' }}</span>
        </button>
        <button
          @click="resubscribeAll"
          :disabled="loadingResubscribe"
          class="btn-action btn-secondary"
          v-ripple
        >
          <svg v-if="!loadingResubscribe" class="icon">
            <use href="#icon-repeat" />
          </svg>
          <span v-if="loadingResubscribe" class="spinner"></span>
          <span>{{ loadingResubscribe ? 'Resubscribing...' : 'Resubscribe All' }}</span>
        </button>
        <button
          @click="deleteAllSubscriptions"
          :disabled="loading || !subscriptions.length"
          class="btn-action btn-danger"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-trash-2" />
          </svg>
          <span>Delete All</span>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-container">
      <LoadingSkeleton v-for="i in 5" :key="i" type="list-item" />
    </div>

    <!-- Empty State -->
    <EmptyState
      v-else-if="!subscriptions.length"
      icon="rss"
      title="No Subscriptions Found"
      description="There are no active EventSub subscriptions. Click refresh to check again."
      action-label="Refresh"
      action-icon="refresh-cw"
      @action="loadSubscriptions"
    />

    <!-- Subscriptions Table -->
    <GlassCard v-else class="table-card">
      <div class="table-wrapper">
        <table class="subscriptions-table">
          <thead>
            <tr>
              <th>Streamer</th>
              <th>Type</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="sub in subscriptions" :key="sub.id" class="table-row">
              <td data-label="Streamer">
                <div class="streamer-cell">
                  <svg class="streamer-icon">
                    <use href="#icon-user" />
                  </svg>
                  <span class="streamer-name">
                    {{ getStreamerName(sub.condition?.broadcaster_user_id) }}
                  </span>
                </div>
              </td>
              <td data-label="Type">
                <span class="type-badge">{{ formatEventType(sub.type) }}</span>
              </td>
              <td data-label="Status">
                <span class="status-badge" :class="`status-${sub.status}`">
                  {{ sub.status }}
                </span>
              </td>
              <td data-label="Created">
                <span class="date-text">{{ formatDate(sub.created_at) }}</span>
              </td>
              <td data-label="Actions">
                <button
                  @click="deleteSubscription(sub.id)"
                  :disabled="loading"
                  class="btn-delete"
                  v-ripple
                  title="Delete subscription"
                >
                  <svg class="icon">
                    <use href="#icon-trash" />
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Table Footer -->
      <div class="table-footer">
        <p class="footer-text">
          Total: <strong>{{ subscriptions.length }}</strong> subscription{{ subscriptions.length !== 1 ? 's' : '' }}
        </p>
      </div>
    </GlassCard>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import GlassCard from '@/components/cards/GlassCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

interface Subscription {
  id: string
  type: string
  status: string
  created_at: string
  broadcaster_id?: string
  broadcaster_name?: string
  condition: {
    broadcaster_user_id: string
  }
}

interface Streamer {
  id: number
  twitch_id: string
  username: string
  profile_image_url?: string
}

const subscriptions = ref<Subscription[]>([])
const streamers = ref<Streamer[]>([])
const streamerMap = ref<Record<string, Streamer>>({})
const loadingResubscribe = ref(false)
const loading = ref(false)

const twitchIdToStreamerMap = computed(() => {
  const map: Record<string, Streamer> = {}
  streamers.value.forEach(streamer => {
    map[streamer.twitch_id] = streamer
  })
  return map
})

function formatEventType(type: string): string {
  switch (type) {
    case 'stream.online':
      return 'Stream Start'
    case 'stream.offline':
      return 'Stream End'
    case 'channel.update':
      return 'Channel Update'
    default:
      return type
  }
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function getStreamerName(twitchId: string): string {
  if (!twitchId) return 'Unknown'

  const streamer = twitchIdToStreamerMap.value[twitchId]

  if (streamer) {
    return streamer.username
  }

  return `Unknown (${twitchId})`
}

async function loadStreamers() {
  try {
    const response = await fetch('/api/streamers', {
      credentials: 'include' // CRITICAL: Required to send session cookie
    })
    const data = await response.json()

    if (Array.isArray(data)) {
      streamers.value = data
    } else if (data.streamers && Array.isArray(data.streamers)) {
      streamers.value = data.streamers
    } else {
      console.error('Unexpected streamer data format:', data)
      streamers.value = []
    }

    streamers.value.forEach(streamer => {
      streamerMap.value[streamer.twitch_id] = streamer
    })

    if (subscriptions.value.length > 0) {
      subscriptions.value = [...subscriptions.value]
    }
  } catch (error) {
    console.error('Failed to load streamers:', error)
  }
}

async function loadSubscriptions() {
  loading.value = true
  try {
    const response = await fetch('/api/streamers/subscriptions', {
      credentials: 'include' // CRITICAL: Required to send session cookie
    })
    const data = await response.json()
    subscriptions.value = data.subscriptions

    await loadStreamers()
  } catch (error) {
    console.error('Failed to load subscriptions:', error)
  } finally {
    loading.value = false
  }
}

async function resubscribeAll() {
  loadingResubscribe.value = true
  try {
    const response = await fetch('/api/streamers/resubscribe-all', {
      method: 'POST',
      credentials: 'include', // CRITICAL: Required to send session cookie
      headers: {
        'Accept': 'application/json'
      }
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Server response:', errorText)
      throw new Error(`Failed to resubscribe: ${response.status}`)
    }

    const data = await response.json()
    alert(`Success: ${data.message}`)

    await loadSubscriptions()

  } catch (error: any) {
    console.error('Failed to resubscribe all:', error.message)
    alert(`Error: ${error.message}`)
  } finally {
    loadingResubscribe.value = false
  }
}

async function deleteSubscription(id: string) {
  // Confirmation dialog
  if (!confirm('Are you sure you want to delete this subscription? This action cannot be undone.')) {
    return
  }
  
  try {
    const response = await fetch(`/api/streamers/subscriptions/${id}`, {
      method: 'DELETE',
      credentials: 'include' // CRITICAL: Required to send session cookie
    })
    if (!response.ok) throw new Error('Failed to delete subscription')

    subscriptions.value = subscriptions.value.filter(sub => sub.id !== id)
  } catch (error) {
    console.error('Failed to delete subscription:', error)
  }
}

async function deleteAllSubscriptions() {
  if (!confirm('Are you sure you want to delete all subscriptions? This action cannot be undone.')) return

  loading.value = true
  try {
    const response = await fetch('/api/streamers/subscriptions', {
      method: 'DELETE',
      credentials: 'include', // CRITICAL: Required to send session cookie
      headers: {
        'Accept': 'application/json'
      }
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Server response:', errorText)
      throw new Error(`Failed to delete subscriptions: ${response.status}`)
    }

    const _data = await response.json()
    alert('All subscriptions successfully deleted!')

    subscriptions.value = []
    await loadSubscriptions()
  } catch (error: any) {
    console.error('Failed to delete all subscriptions:', error.message)
    alert(`Error: ${error.message}`)
  } finally {
    loading.value = false
  }
}

onMounted(loadSubscriptions)
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.subscriptions-view {
  // .page-view provides padding/sizing via global styles
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

// Header
.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-8);
  gap: var(--spacing-4);
  flex-wrap: wrap;
}

.header-content {
  margin-bottom: var(--spacing-6);
  flex: 1;
  min-width: 200px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-3);
}

.icon-title {
  width: 32px;
  height: 32px;
  fill: var(--color-primary);
}

.page-subtitle {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--spacing-3);
  flex-wrap: wrap;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-5);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    filter: grayscale(0.3);
  }

  &.btn-primary {
    background: var(--gradient-primary);
    color: white; /* Always white on gradient background */

    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: var(--shadow-lg);
    }

    &:disabled {
      background: var(--background-secondary);
      color: var(--text-tertiary);
      border: 1px solid var(--border-color);
    }
  }

  &.btn-secondary {
    background: var(--background-secondary);
    color: var(--text-primary); /* ✅ Theme-aware: dark text in light mode, light text in dark mode */
    border: 1px solid var(--border-color);

    &:hover:not(:disabled) {
      background: var(--background-tertiary);
      border-color: var(--color-primary);
    }

    &:disabled {
      background: var(--background-tertiary);
      color: var(--text-tertiary);
      border-color: var(--border-color);
    }
  }

  &.btn-danger {
    background: var(--color-error);
    color: white; /* Always white on error background */

    &:hover:not(:disabled) {
      background: var(--color-error-hover);
      transform: translateY(-2px);
      box-shadow: var(--shadow-lg);
    }

    &:disabled {
      background: var(--background-secondary);
      color: var(--text-tertiary);
      border: 1px solid var(--border-color);
    }
  }
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

// Loading
.loading-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

// Table
.table-card {
  padding: 0;
  overflow: hidden;
}

.table-wrapper {
  overflow-x: auto;
}

.subscriptions-table {
  width: 100%;
  border-collapse: collapse;

  thead {
    background: var(--background-tertiary);

    th {
      padding: var(--spacing-4) var(--spacing-5);
      text-align: left;
      font-size: var(--font-size-sm);
      font-weight: var(--font-weight-semibold);
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }
  }

  tbody {
    tr {
      border-bottom: 1px solid var(--border-color);
      transition: background 0.2s ease;

      &:hover {
        background: rgba(var(--color-primary-rgb), 0.03);
      }

      &:last-child {
        border-bottom: none;
      }
    }

    td {
      padding: var(--spacing-4) var(--spacing-5);
      font-size: var(--font-size-sm);
      color: var(--text-primary);
    }
  }
}

.streamer-cell {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.streamer-icon {
  width: 20px;
  height: 20px;
  fill: var(--text-tertiary);
  flex-shrink: 0;
}

.streamer-name {
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.type-badge {
  display: inline-block;
  padding: var(--spacing-1) var(--spacing-3);
  background: rgba(var(--color-primary-rgb), 0.1);
  color: var(--color-primary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}

.status-badge {
  display: inline-block;
  padding: var(--spacing-1) var(--spacing-3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  text-transform: capitalize;

  &.status-enabled,
  &.status-active {
    background: rgba(var(--color-success-rgb), 0.1);
    color: var(--color-success);
  }

  &.status-disabled,
  &.status-webhook_callback_verification_pending {
    background: rgba(var(--color-warning-rgb), 0.1);
    color: var(--color-warning);
  }

  &.status-failed {
    background: rgba(var(--color-error-rgb), 0.1);
    color: var(--color-error);
  }
}

.date-text {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}

.btn-delete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;

  .icon {
    width: 16px;
    height: 16px;
    stroke: var(--text-secondary);
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  &:hover:not(:disabled) {
    background: rgba(var(--color-error-rgb), 0.1);
    border-color: var(--color-error);

    .icon {
      stroke: var(--color-error);
    }
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// Table Footer
.table-footer {
  padding: var(--spacing-4) var(--spacing-5);
  background: var(--background-tertiary);
  border-top: 1px solid var(--border-color);
}

.footer-text {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);

  strong {
    color: var(--text-primary);
    font-weight: var(--font-weight-semibold);
  }
}

// Responsive
@include m.respond-below('md') {  // < 768px
  .subscriptions-view {
    padding: var(--spacing-4);
  }

  .page-title {
    font-size: var(--font-size-2xl);
  }

  .icon-title {
    width: 24px;
    height: 24px;
  }

  .header-actions {
    flex-direction: column;

    .btn-action {
      width: 100%;
      justify-content: center;
    }
  }

  // Mobile table
  .subscriptions-table {
    thead {
      display: none;
    }

    tbody {
      tr {
        display: block;
        margin-bottom: var(--spacing-4);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        padding: var(--spacing-4);

        &:hover {
          background: var(--background-secondary);
        }
      }

      td {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--spacing-2) 0;
        border: none;

        &::before {
          content: attr(data-label);
          font-weight: var(--font-weight-semibold);
          color: var(--text-secondary);
          font-size: var(--font-size-xs);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        &:last-child {
          justify-content: flex-end;
          padding-top: var(--spacing-3);
          margin-top: var(--spacing-2);
          border-top: 1px solid var(--border-color);

          &::before {
            display: none;
          }
        }
      }
    }
  }
}
</style>
