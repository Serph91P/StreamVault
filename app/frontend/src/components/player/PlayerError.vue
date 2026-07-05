<template>
  <div class="player-error" role="alert">
    <div class="player-error-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
    </div>
    <div class="player-error-copy">
      <h3>{{ title }}</h3>
      <p>{{ message }}</p>
    </div>
    <BaseButton v-if="actionLabel" variant="primary" size="sm" @click="emit('action')">{{ actionLabel }}</BaseButton>
  </div>
</template>

<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'

interface Props {
  title: string
  message: string
  actionLabel?: string
}

defineProps<Props>()
const emit = defineEmits<{ action: [] }>()
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.player-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-4);
  max-width: 420px;
  margin: 0 auto;
  padding: var(--spacing-6);
  color: var(--text-primary);
  text-align: center;
}

.player-error-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border: 1px solid rgba(var(--danger-color-rgb), 0.3);
  border-radius: var(--radius-full);
  background: rgba(var(--danger-color-rgb), 0.12);
  color: var(--danger-color);

  svg { width: 28px; height: 28px; }
}

.player-error-copy {
  h3 {
    margin: 0 0 var(--spacing-2);
    font-size: var(--text-xl);
    font-weight: v.$font-semibold;
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    line-height: v.$leading-relaxed;
  }
}
</style>
