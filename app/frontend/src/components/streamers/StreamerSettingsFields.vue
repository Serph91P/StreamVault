<script setup lang="ts">
/**
 * Renders streamer settings (notifications + recording + quality) from
 * STREAMER_FIELD_GROUPS so AddStreamerForm and StreamerDetail share one
 * source of truth. No per-page hardcoded markup, no phantom fields.
 */
import { computed } from 'vue'
import { STREAMER_FIELD_GROUPS, type FieldSchema } from '@/schemas/streamerSettings.schema'

interface Props {
  /** Reactive state object: { quality, notifications: {...}, recording: {...} } */
  modelValue: Record<string, unknown>
  /** Disable all inputs while submitting */
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), { disabled: false })

const emit = defineEmits<{
  (e: 'update:modelValue', v: Record<string, unknown>): void
}>()

const state = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function getValue(payloadKey: 'recording' | 'notifications' | 'root', field: FieldSchema): unknown {
  if (payloadKey === 'root') return state.value[field.key]
  const bucket = state.value[payloadKey] as Record<string, unknown> | undefined
  return bucket?.[field.key]
}

function setValue(
  payloadKey: 'recording' | 'notifications' | 'root',
  field: FieldSchema,
  value: unknown,
) {
  if (payloadKey === 'root') {
    state.value = { ...state.value, [field.key]: value }
    return
  }
  const bucket = { ...((state.value[payloadKey] as Record<string, unknown>) || {}) }
  bucket[field.key] = value
  state.value = { ...state.value, [payloadKey]: bucket }
}

function isVisible(field: FieldSchema): boolean {
  if (!field.dependsOn) return true
  return field.dependsOn(state.value)
}
</script>

<template>
  <div class="streamer-settings-fields">
    <section
      v-for="group in STREAMER_FIELD_GROUPS"
      :key="group.id"
      class="settings-section"
    >
      <h4>{{ group.title }}</h4>

      <div :class="['fields-grid', `grid-${group.id}`]">
        <template v-for="field in group.fields" :key="field.key">
          <div v-if="isVisible(field)" class="field-row" :class="`field-${field.type}`">
            <!-- checkbox -->
            <label v-if="field.type === 'checkbox'" class="checkbox-container">
              <input
                type="checkbox"
                :checked="Boolean(getValue(group.payloadKey, field))"
                :disabled="disabled"
                @change="setValue(group.payloadKey, field, ($event.target as HTMLInputElement).checked)"
              />
              <span class="checkmark"></span>
              <div class="option-text">
                <span class="option-title">{{ field.label }}</span>
                <span v-if="field.help" class="option-description">{{ field.help }}</span>
              </div>
            </label>

            <!-- select -->
            <div v-else-if="field.type === 'select'" class="form-group">
              <label :for="`field-${group.id}-${field.key}`">{{ field.label }}:</label>
              <select
                :id="`field-${group.id}-${field.key}`"
                class="input-field"
                :disabled="disabled"
                :value="String(getValue(group.payloadKey, field) ?? '')"
                @change="setValue(group.payloadKey, field, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
              <div v-if="field.help" class="help-text">{{ field.help }}</div>
            </div>

            <!-- text -->
            <div v-else-if="field.type === 'text'" class="form-group">
              <label :for="`field-${group.id}-${field.key}`">{{ field.label }}:</label>
              <input
                :id="`field-${group.id}-${field.key}`"
                type="text"
                class="input-field"
                :disabled="disabled"
                :placeholder="field.placeholder"
                :value="String(getValue(group.payloadKey, field) ?? '')"
                @input="setValue(group.payloadKey, field, ($event.target as HTMLInputElement).value)"
              />
              <div v-if="field.help" class="help-text">{{ field.help }}</div>
            </div>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.settings-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);

  &:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
  }

  h4 {
    margin-top: 0;
    margin-bottom: 1rem;
    color: var(--text-primary);
    font-size: 1.1rem;
    font-weight: 600;
  }
}

.fields-grid {
  display: grid;
  gap: 1rem;
}

.fields-grid.grid-notifications {
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
}

.fields-grid.grid-recording {
  grid-template-columns: 1fr;
}

.fields-grid.grid-quality {
  grid-template-columns: 1fr;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;

  label {
    font-weight: 500;
    color: var(--text-primary);
    font-size: 0.9rem;
  }
}

.help-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.checkbox-container {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  cursor: pointer;
  user-select: none;

  input[type='checkbox'] {
    margin-top: 0.2rem;
    accent-color: var(--color-primary);
  }

  .checkmark {
    display: none;
  }

  .option-title {
    display: block;
    font-weight: 500;
    color: var(--text-primary);
  }

  .option-description {
    display: block;
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.15rem;
  }
}
</style>
