<script setup lang="ts">
import { computed } from 'vue'
import EmptyState, { type EmptyStateTone } from '@/components/EmptyState.vue'

interface Props {
  state: 'empty' | 'loading' | 'error'
  title: string
  message: string
  actionLabel?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ action: [] }>()

const stateTone = computed<EmptyStateTone>(() => {
  if (props.state === 'error') return 'danger'
  if (props.state === 'loading') return 'info'
  return 'neutral'
})

const stateIcon = computed(() => {
  if (props.state === 'error') return 'alert-circle'
  if (props.state === 'loading') return 'refresh-cw'
  return 'bell'
})

const stateToneLabel = computed(() => {
  if (props.state === 'error') return 'Notification error'
  if (props.state === 'loading') return 'Notifications loading'
  return 'Notification empty state'
})
</script>

<template>
  <EmptyState
    class="notification-state"
    :class="`notification-state-${state}`"
    variant="compact"
    :tone="stateTone"
    :role="state === 'error' ? 'alert' : 'status'"
    :icon="stateIcon"
    :loading="state === 'loading'"
    :tone-label="stateToneLabel"
    :title="title"
    :description="message"
    :retry-label="state === 'error' ? actionLabel : undefined"
    @retry="emit('action')"
  />
</template>

<style scoped lang="scss">
.notification-state {
  min-height: 18rem;
  padding: var(--spacing-8) var(--spacing-5);
}
</style>
