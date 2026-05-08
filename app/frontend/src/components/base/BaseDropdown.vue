<script setup lang="ts">
import { computed, useAttrs, useId } from 'vue'

interface Option {
  label: string
  value: string | number
  disabled?: boolean
}

interface Props {
  modelValue: string | number | null | undefined
  /** Options as { label, value, disabled? }. If omitted, use the default slot for <option>. */
  options?: Option[]
  label?: string
  /** First option that is shown when the value is empty/null. */
  placeholder?: string
  state?: 'default' | 'error' | 'success'
  error?: string
  hint?: string
  required?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  state: 'default',
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: string | number): void
  (e: 'change', v: string | number): void
}>()

defineOptions({ inheritAttrs: false })
const attrs = useAttrs()

const id = useId()
const errorId = computed(() => `${id}-error`)
const hintId = computed(() => `${id}-hint`)

const effectiveState = computed<'default' | 'error' | 'success'>(() =>
  props.error ? 'error' : props.state,
)

const selectClasses = computed(() => [
  effectiveState.value === 'error' && 'error',
  effectiveState.value === 'success' && 'success',
])

const describedBy = computed(() => {
  if (props.error) return errorId.value
  if (props.hint) return hintId.value
  return undefined
})

function onChange(ev: Event) {
  const v = (ev.target as HTMLSelectElement).value
  emit('update:modelValue', v)
  emit('change', v)
}
</script>

<template>
  <div class="form-group">
    <label v-if="label" :for="id" :class="{ required }">{{ label }}</label>
    <select
      :id="id"
      v-bind="attrs"
      :value="modelValue ?? ''"
      :class="selectClasses"
      :required="required"
      :disabled="disabled"
      :aria-invalid="effectiveState === 'error' || undefined"
      :aria-describedby="describedBy"
      @change="onChange"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <template v-if="options">
        <option
          v-for="opt in options"
          :key="opt.value"
          :value="opt.value"
          :disabled="opt.disabled"
        >
          {{ opt.label }}
        </option>
      </template>
      <slot v-else />
    </select>
    <small v-if="error" :id="errorId" class="form-error">{{ error }}</small>
    <small v-else-if="hint" :id="hintId" class="form-hint">{{ hint }}</small>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.form-error {
  display: block;
  margin-top: v.$spacing-2;
  color: var(--danger-color);
  font-size: v.$text-sm;
}
.form-hint {
  display: block;
  margin-top: v.$spacing-2;
  color: var(--text-secondary);
  font-size: v.$text-sm;
}
</style>
