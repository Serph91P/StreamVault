<script setup lang="ts">
interface Props {
  state: 'empty' | 'loading' | 'error'
  title: string
  message: string
}

defineProps<Props>()
</script>

<template>
  <div class="notification-state" :class="`notification-state-${state}`" role="status">
    <div class="notification-state-icon" aria-hidden="true">
      <svg v-if="state === 'loading'" class="state-svg state-spinner"><use href="#icon-refresh-cw" /></svg>
      <svg v-else-if="state === 'error'" class="state-svg"><use href="#icon-alert-circle" /></svg>
      <svg v-else class="state-svg"><use href="#icon-bell" /></svg>
    </div>
    <h3>{{ title }}</h3>
    <p>{{ message }}</p>
  </div>
</template>

<style scoped lang="scss">
.notification-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 18rem;
  padding: var(--spacing-8) var(--spacing-5);
  text-align: center;
  color: var(--text-secondary);
}

.notification-state-icon {
  display: grid;
  place-items: center;
  width: 4rem;
  height: 4rem;
  margin-bottom: var(--spacing-4);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  background: var(--glass-bg-subtle);
}

.state-svg {
  width: 1.75rem;
  height: 1.75rem;
  stroke: currentColor;
  fill: none;
}

.state-spinner {
  animation: spin 1s linear infinite;
}

.notification-state h3 {
  margin: 0 0 var(--spacing-2);
  color: var(--text-primary);
  font-size: var(--text-lg);
  font-weight: 700;
}

.notification-state p {
  max-width: 18rem;
  margin: 0;
  font-size: var(--text-sm);
  line-height: 1.5;
}

.notification-state-error .notification-state-icon {
  color: var(--danger-color);
  border-color: rgba(244, 67, 54, 0.35);
  background: rgba(244, 67, 54, 0.1);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
