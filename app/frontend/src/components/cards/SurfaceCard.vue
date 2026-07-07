<script setup lang="ts">
import { computed, useId, useSlots } from 'vue'
import GlassCard from '@/components/cards/GlassCard.vue'
import type { GlassVariant, PaddingSize } from '@/components/cards/GlassCard.vue'

interface Props {
  tag?: string
  variant?: GlassVariant
  padding?: boolean | PaddingSize
  elevated?: boolean
  hoverable?: boolean
  clickable?: boolean
  disabled?: boolean
  loading?: boolean
  labelledBy?: string
  describedBy?: string
}

const props = withDefaults(defineProps<Props>(), {
  tag: 'section',
  variant: 'medium',
  padding: true,
  elevated: false,
  hoverable: false,
  clickable: false,
  disabled: false,
  loading: false,
})

const emit = defineEmits<{
  click: [event: MouseEvent | KeyboardEvent]
}>()

const slots = useSlots()
const generatedTitleId = useId()
const titleId = computed(() => props.labelledBy || (slots.title ? generatedTitleId : undefined))

function onClick(event: MouseEvent | KeyboardEvent) {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>

<template>
  <GlassCard
    :tag="tag"
    :variant="variant"
    :padding="padding"
    :elevated="elevated"
    :hoverable="hoverable"
    :clickable="clickable"
    :disabled="disabled"
    :loading="loading"
    class="surface-card"
    :labelled-by="titleId"
    :described-by="describedBy"
    @click="onClick"
  >
    <header v-if="$slots.header || $slots.title || $slots.actions" class="surface-card-header">
      <div class="surface-card-heading">
        <slot name="header">
          <h2 v-if="$slots.title" :id="titleId" class="surface-card-title">
            <slot name="title" />
          </h2>
          <p v-if="$slots.description" class="surface-card-description">
            <slot name="description" />
          </p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="surface-card-actions">
        <slot name="actions" />
      </div>
    </header>

    <div class="surface-card-body">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="surface-card-footer">
      <slot name="footer" />
    </footer>
  </GlassCard>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.surface-card {
  min-width: 0;
}

.surface-card-header,
.surface-card-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);
}

.surface-card-header {
  margin-bottom: var(--spacing-4);
}

.surface-card-footer {
  margin-top: var(--spacing-4);
  padding-top: var(--spacing-4);
  border-top: 1px solid var(--border-color);
}

.surface-card-heading,
.surface-card-body {
  min-width: 0;
}

.surface-card-title {
  margin: 0;
  color: var(--text-primary);
  font-size: v.$text-xl;
  font-weight: v.$font-semibold;
  line-height: v.$leading-tight;
}

.surface-card-description {
  margin: var(--spacing-1) 0 0;
  color: var(--text-secondary);
  font-size: v.$text-sm;
  line-height: v.$leading-relaxed;
}

.surface-card-actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--spacing-2);
}
</style>
