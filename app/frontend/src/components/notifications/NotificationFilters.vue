<script setup lang="ts">
import type { NotificationFilter } from '@/stores/notifications'

interface TypeOption {
  value: string
  label: string
  count: number
}

interface Props {
  modelValue: NotificationFilter
  totalCount: number
  unreadCount: number
  severityCounts: Record<string, number>
  typeOptions: TypeOption[]
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: NotificationFilter): void
}>()

const severityFilters = [
  { value: 'critical', label: 'Critical' },
  { value: 'error', label: 'Errors' },
  { value: 'warning', label: 'Warnings' },
  { value: 'success', label: 'Success' },
  { value: 'info', label: 'Info' }
]

function updateFilter(value: NotificationFilter) {
  emit('update:modelValue', value)
}
</script>

<template>
  <div class="notification-filters" aria-label="Notification filters">
    <div class="filter-row primary-filters">
      <button
        type="button"
        class="filter-chip"
        :class="{ active: modelValue === 'all' }"
        @click="updateFilter('all')"
      >
        All
        <span>{{ totalCount }}</span>
      </button>
      <button
        type="button"
        class="filter-chip unread-chip"
        :class="{ active: modelValue === 'unread' }"
        @click="updateFilter('unread')"
      >
        Unread
        <span>{{ unreadCount }}</span>
      </button>
    </div>

    <div class="filter-row" aria-label="Severity filters">
      <button
        v-for="filter in severityFilters"
        :key="filter.value"
        type="button"
        class="filter-chip compact"
        :class="[`severity-${filter.value}`, { active: modelValue === filter.value }]"
        :disabled="!severityCounts[filter.value]"
        @click="updateFilter(filter.value)"
      >
        {{ filter.label }}
        <span>{{ severityCounts[filter.value] || 0 }}</span>
      </button>
    </div>

    <div v-if="typeOptions.length" class="filter-row type-filters" aria-label="Event type filters">
      <button
        v-for="option in typeOptions"
        :key="option.value"
        type="button"
        class="filter-chip type-chip"
        :class="{ active: modelValue === option.value }"
        @click="updateFilter(option.value)"
      >
        {{ option.label }}
        <span>{{ option.count }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.notification-filters {
  display: grid;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
  border-bottom: 1px solid var(--glass-border);
  background: linear-gradient(180deg, var(--glass-bg-medium), transparent);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 2.25rem;
  padding: 0 var(--spacing-3);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  background: var(--glass-bg-subtle);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--duration-200) var(--ease-out), background var(--duration-200) var(--ease-out), color var(--duration-200) var(--ease-out);
}

.filter-chip span {
  min-width: 1.35rem;
  padding: 0.125rem 0.4rem;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
  font-size: var(--text-xs);
  text-align: center;
}

.filter-chip:hover:not(:disabled),
.filter-chip.active {
  border-color: var(--primary-color);
  background: rgba(145, 71, 255, 0.14);
  color: var(--text-primary);
}

.filter-chip:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.filter-chip.compact {
  min-height: 2rem;
  font-size: var(--text-xs);
}

.unread-chip.active {
  border-color: var(--info-color);
  background: rgba(0, 180, 216, 0.14);
}

.severity-critical.active,
.severity-error.active {
  border-color: var(--danger-color);
  background: rgba(244, 67, 54, 0.14);
}

.severity-warning.active {
  border-color: var(--warning-color);
  background: rgba(255, 152, 0, 0.14);
}

.severity-success.active {
  border-color: var(--success-color);
  background: rgba(29, 185, 84, 0.14);
}

.type-filters {
  max-height: 5.5rem;
  overflow: auto;
  padding-right: var(--spacing-1);
}

.type-chip {
  text-transform: capitalize;
}

@media (max-width: 767px) {
  .notification-filters {
    padding: var(--spacing-3) var(--spacing-4);
  }

  .filter-row {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: var(--spacing-1);
  }

  .filter-chip {
    flex: 0 0 auto;
  }
}
</style>
