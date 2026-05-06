<script setup lang="ts">
import { computed, useAttrs, useId } from 'vue'

interface Props {
  modelValue: string | number | null | undefined
  label?: string
  /** Native input type. Default 'text'. */
  type?:
    | 'text'
    | 'email'
    | 'password'
    | 'number'
    | 'url'
    | 'search'
    | 'tel'
  /** Validation/visual state */
  state?: 'default' | 'error' | 'success'
  /** Error message displayed below the input. Implies state='error'. */
  error?: string
  /** Helper text below the input (when no error). */
  hint?: string
  required?: boolean
  disabled?: boolean
  placeholder?: string
  /** Render label as required (adds asterisk via .required class) */
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  state: 'default',
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: string | number): void
}>()

defineOptions({ inheritAttrs: false })
const attrs = useAttrs()

const id = useId()
const errorId = computed(() => `${id}-error`)
const hintId = computed(() => `${id}-hint`)

const effectiveState = computed<'default' | 'error' | 'success'>(() =>
  props.error ? 'error' : props.state,
)

const inputClasses = computed(() => [
  'input-field',
  effectiveState.value === 'error' && 'error',
  effectiveState.value === 'success' && 'success',
])

const describedBy = computed(() => {
  const ids: string[] = []
  if (props.error) ids.push(errorId.value)
  else if (props.hint) ids.push(hintId.value)
  return ids.length ? ids.join(' ') : undefined
})

function onInput(ev: Event) {
  const target = ev.target as HTMLInputElement
  const v = props.type === 'number' ? target.valueAsNumber : target.value
  emit('update:modelValue', v as string | number)
}
</script>

<template>
  <div class="form-group">
    <label v-if="label" :for="id" :class="{ required }">{{ label }}</label>
    <input
      :id="id"
      v-bind="attrs"
      :type="type"
      :value="modelValue"
      :class="inputClasses"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :aria-invalid="effectiveState === 'error' || undefined"
      :aria-describedby="describedBy"
      @input="onInput"
    >
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
