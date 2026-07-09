<script setup lang="ts">
import { computed, useId } from 'vue'

interface Props {
  label?: string
  error?: string
  success?: string
  hint?: string
  state?: 'default' | 'error' | 'success'
  required?: boolean
  disabled?: boolean
  forId?: string
  describedBy?: string
}

const props = defineProps<Props>()

const generatedId = useId()
const inputId = computed(() => props.forId || generatedId)
const errorId = computed(() => `${inputId.value}-error`)
const successId = computed(() => `${inputId.value}-success`)
const hintId = computed(() => `${inputId.value}-hint`)
const effectiveState = computed<'default' | 'error' | 'success'>(() =>
  props.error ? 'error' : props.state || 'default',
)
const describedBy = computed(() => {
  const ids: string[] = []
  if (props.describedBy) ids.push(props.describedBy)
  if (props.error) ids.push(errorId.value)
  else if (props.success) ids.push(successId.value)
  else if (props.hint) ids.push(hintId.value)
  return ids.length ? ids.join(' ') : undefined
})
</script>

<template>
  <div
    class="form-group form-field"
    :class="{
      'has-error': effectiveState === 'error',
      'has-success': effectiveState === 'success',
      'is-disabled': disabled,
    }"
  >
    <label v-if="label" :for="inputId" :class="{ required }">{{ label }}</label>
    <slot
      :id="inputId"
      :described-by="describedBy"
      :invalid="effectiveState === 'error'"
      :state="effectiveState"
      :disabled="disabled"
    />
    <small v-if="error" :id="errorId" class="form-error">{{ error }}</small>
    <small v-else-if="success" :id="successId" class="form-success">{{ success }}</small>
    <small v-else-if="hint" :id="hintId" class="form-hint">{{ hint }}</small>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.form-field {
  min-width: 0;
}

.form-error,
.form-success,
.form-hint {
  display: block;
  margin-top: var(--spacing-2);
  font-size: v.$text-sm;
}

.form-error {
  color: var(--danger-color);
}

.form-success {
  color: var(--success-color);
}

.form-hint {
  color: var(--text-secondary);
}

.is-disabled {
  opacity: 0.7;
}
</style>
