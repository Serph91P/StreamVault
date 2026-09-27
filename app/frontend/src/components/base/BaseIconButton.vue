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
    class="base-icon-button base-icon-button-target--icon unstyled"
    :type="type"
    :disabled="disabled"
    :aria-label="label"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<style scoped lang="scss">
.base-icon-button-target--icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--sv-cmp-button-height-primary);
  min-width: var(--sv-cmp-button-height-primary);
  height: var(--sv-cmp-button-height-primary);
  min-height: var(--sv-cmp-button-height-primary);
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
    outline: 2px solid var(--sv-cmp-button-focus);
    outline-offset: 2px;
  }

  &:disabled {
    color: var(--sv-cmp-button-disabled-foreground);
    background: var(--sv-cmp-button-disabled-background);
    cursor: not-allowed;
  }
}
</style>
