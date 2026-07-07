<template>
  <div class="player-status" :class="`player-status-${state}`">
    <div class="player-status-visual" aria-hidden="true">
      <div v-if="state === 'loading'" class="status-spinner" />
      <div v-else-if="state === 'buffering'" class="status-pulse"><span /><span /><span /></div>
      <div v-else-if="state === 'live'" class="status-live-dot" />
      <div v-else-if="state === 'stopped'" class="status-stopped-icon">
        <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
      </div>
      <svg v-else class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" /><path d="M12 8v4l3 3" /></svg>
    </div>
    <StatusBadge :tone="statusBadgeTone" size="sm" :dot="badgeDot" :pulse="badgePulse">{{ label }}</StatusBadge>
    <p v-if="message" class="player-status-message">{{ message }}</p>
    <p v-if="retryCount !== undefined && retryCount > 0" class="player-status-retry">Retry attempt {{ retryCount }}/{{ maxRetries }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge, { type StatusBadgeTone } from '@/components/base/StatusBadge.vue'

export type PlayerState = 'loading' | 'buffering' | 'connecting' | 'live' | 'offline' | 'idle' | 'stopped' | 'error'

interface Props {
  state: PlayerState
  message?: string
  retryCount?: number
  maxRetries?: number
}

const props = withDefaults(defineProps<Props>(), { maxRetries: 10 })

const label = computed(() => ({
  loading: 'Loading',
  buffering: 'Buffering',
  connecting: 'Connecting',
  live: 'Live',
  offline: 'Offline',
  idle: 'Idle',
  stopped: 'Stopped',
  error: 'Error'
}[props.state]))

const statusBadgeTone = computed<StatusBadgeTone>(() => {
  const tones: Record<PlayerState, StatusBadgeTone> = {
    loading: 'neutral',
    buffering: 'warning',
    connecting: 'info',
    live: 'live',
    offline: 'offline',
    idle: 'neutral',
    stopped: 'offline',
    error: 'warning'
  }
  return tones[props.state]
})

const badgeDot = computed(() => props.state === 'live' || props.state === 'buffering' || props.state === 'connecting')
const badgePulse = computed(() => props.state === 'live' || props.state === 'buffering' || props.state === 'error')
</script>

<style scoped lang="scss">
.player-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-3);
  padding: var(--spacing-6);
  color: var(--text-primary);
  text-align: center;
}

.player-status-visual {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
}

.status-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(var(--primary-color-rgb), 0.18);
  border-top-color: var(--primary-color);
  border-radius: var(--radius-full);
  animation: spin 1s linear infinite;
}

.status-pulse {
  display: inline-flex;
  gap: 5px;

  span {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
    background: var(--warning-color);
    animation: pulse-dot 1.2s ease-in-out infinite;
  }
}

.status-live-dot {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  background: var(--danger-color);
  box-shadow: 0 0 0 8px rgba(var(--danger-color-rgb), 0.14);
  animation: pulse-dot 1.6s ease-in-out infinite;
}

.status-icon {
  width: 32px;
  height: 32px;
  color: var(--text-secondary);
}

.status-stopped-icon {
  width: 32px;
  height: 32px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.player-status-message,
.player-status-retry {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.5;
}

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse-dot { 50% { opacity: 1; transform: scale(1.08); } }
</style>
