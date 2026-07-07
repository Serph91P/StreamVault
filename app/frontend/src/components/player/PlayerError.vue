<template>
  <EmptyState
    class="player-error"
    variant="compact"
    tone="danger"
    role="alert"
    icon="alert-triangle"
    tone-label="Critical playback error"
    :title="title"
    :description="message"
    :retry-label="actionLabel"
    retry-variant="primary"
    @retry="emit('action')"
  />
</template>

<script setup lang="ts">
import EmptyState from '@/components/EmptyState.vue'

interface Props {
  title: string
  message: string
  actionLabel?: string
}

defineProps<Props>()
const emit = defineEmits<{ action: [] }>()
</script>

<style scoped lang="scss">
.player-error {
  max-width: 420px;
  min-height: 0;
  margin: 0 auto;
  padding: var(--spacing-6);

  :deep(.empty-description) {
    color: var(--text-primary);
  }
}
</style>
