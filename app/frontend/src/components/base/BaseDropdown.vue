<script setup lang="ts">
import { computed, useAttrs, useId } from 'vue'

interface Option {
  label: string
  value: string | number
  disabled?: boolean
}

interface Props {
  modelValue: string | number | null | undefined
  id?: string
  /** Options as { label, value, disabled? }. If omitted, use the default slot for <option>. */
  options?: Option[]
  label?: string
  /** First option that is shown when the value is empty/null. */
  placeholder?: string
  state?: 'default' | 'error' | 'success'
  error?: string
  success?: string
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

const generatedId = useId()
const selectId = computed(() => props.id || generatedId)
const errorId = computed(() => `${selectId.value}-error`)
const successId = computed(() => `${selectId.value}-success`)
const hintId = computed(() => `${selectId.value}-hint`)

const effectiveState = computed<'default' | 'error' | 'success'>(() =>
  props.error ? 'error' : props.state,
)

const selectClasses = computed(() => [
  'base-form-control-target',
  effectiveState.value === 'error' && 'error',
  effectiveState.value === 'success' && 'success',
])

const describedBy = computed(() => {
  const ids: string[] = []
  const externalDescribedBy = attrs['aria-describedby']
  if (typeof externalDescribedBy === 'string') ids.push(externalDescribedBy)
  if (props.error) ids.push(errorId.value)
  else if (props.success) ids.push(successId.value)
  else if (props.hint) ids.push(hintId.value)
  return ids.length ? ids.join(' ') : undefined
})

function onChange(ev: Event) {
  const raw = (ev.target as HTMLSelectElement).value
  const v = props.options?.find(option => String(option.value) === raw)?.value ?? raw
  emit('update:modelValue', v)
  emit('change', v)
}
</script>

<template>
  <div class="form-group">
    <label v-if="label" :for="selectId" :class="{ required }">{{ label }}</label>
    <select
      v-bind="attrs"
      :id="selectId"
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
    <small v-else-if="success" :id="successId" class="form-success">{{ success }}</small>
    <small v-else-if="hint" :id="hintId" class="form-hint">{{ hint }}</small>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.base-form-control-target {
  min-height: var(--sv-fdn-size-target);
  background: var(--sv-cmp-field-background);
  border-color: var(--sv-cmp-field-border);
  // The legacy global select reset uses a fixed SVG that disappears in some
  // light-theme cascades. The native indicator follows the active color scheme.
  appearance: auto;
  background-image: none;
  color-scheme: light dark;

  &:hover:not(:disabled) { border-color: var(--sv-cmp-field-border-hover); }
  &:focus-visible { border-color: var(--sv-cmp-field-border-focus); }
  &.error { border-color: var(--sv-cmp-field-error); }
}

.form-error {
  display: block;
  margin-top: v.$spacing-2;
  color: var(--danger-color);
  font-size: v.$text-sm;
}
.form-success {
  display: block;
  margin-top: v.$spacing-2;
  color: var(--success-color);
  font-size: v.$text-sm;
}
.form-hint {
  display: block;
  margin-top: v.$spacing-2;
  color: var(--text-secondary);
  font-size: v.$text-sm;
}
</style>
