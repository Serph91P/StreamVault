<script setup lang="ts">
import { computed, useId } from 'vue'

interface Props {
  label?: string
  error?: string
  hint?: string
  required?: boolean
  forId?: string
}

const props = defineProps<Props>()

const generatedId = useId()
const inputId = computed(() => props.forId || generatedId)
const errorId = computed(() => `${inputId.value}-error`)
const hintId = computed(() => `${inputId.value}-hint`)
const describedBy = computed(() => {
  if (props.error) return errorId.value
  if (props.hint) return hintId.value
  return undefined
})
</script>

<template>
  <div class="form-group form-field" :class="{ 'has-error': error }">
    <label v-if="label" :for="inputId" :class="{ required }">{{ label }}</label>
    <slot :id="inputId" :described-by="describedBy" :invalid="Boolean(error)" />
    <small v-if="error" :id="errorId" class="form-error">{{ error }}</small>
    <small v-else-if="hint" :id="hintId" class="form-hint">{{ hint }}</small>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.form-field {
  min-width: 0;
}

.form-error,
.form-hint {
  display: block;
  margin-top: var(--spacing-2);
  font-size: v.$text-sm;
}

.form-error {
  color: var(--danger-color);
}

.form-hint {
  color: var(--text-secondary);
}
</style>
