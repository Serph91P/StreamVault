<script setup lang="ts">
interface Props {
  label: string
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
}

withDefaults(defineProps<Props>(), {
  type: 'button',
  disabled: false,
})

defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()
</script>

<template>
  <button
    class="base-icon-button unstyled"
    :type="type"
    :disabled="disabled"
    :aria-label="label"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.base-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--control-target-min);
  min-width: var(--control-target-min);
  height: var(--control-target-min);
  min-height: var(--control-target-min);
  padding: 0;
  color: inherit;
  background: transparent;
  border: 0;
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background-color var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);

  &:focus-visible {
    outline: var(--focus-ring);
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @include m.respond-below('md') {
    width: var(--control-target-mobile);
    min-width: var(--control-target-mobile);
    height: var(--control-target-mobile);
    min-height: var(--control-target-mobile);
  }
}
</style>
