<script setup lang="ts">
import { computed, ref } from 'vue'
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
  sourceOptions: TypeOption[]
  typeOptions: TypeOption[]
}

const props = defineProps<Props>()

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

const showFilterMenu = ref(false)

const activeFilterLabel = computed(() => {
  if (props.modelValue === 'all') return 'All notifications'
  if (props.modelValue === 'unread') return 'Unread only'

  const severity = severityFilters.find(filter => filter.value === props.modelValue)
  if (severity) return severity.label

  return props.sourceOptions.find(option => option.value === props.modelValue)?.label
    || props.typeOptions.find(option => option.value === props.modelValue)?.label
    || 'Filtered'
})

function updateFilter(value: NotificationFilter) {
  emit('update:modelValue', value)
  showFilterMenu.value = false
}
</script>

<template>
  <div class="notification-filters" aria-label="Notification filters">
    <div class="filter-summary-row">
      <button
        type="button"
        class="filter-menu-toggle"
        :aria-expanded="showFilterMenu"
        aria-controls="notification-filter-menu"
        @click="showFilterMenu = !showFilterMenu"
      >
        <svg class="filter-icon" aria-hidden="true">
          <use href="#icon-filter" />
        </svg>
        Filter
        <span class="active-filter-label">{{ activeFilterLabel }}</span>
      </button>
    </div>

    <div v-if="showFilterMenu" id="notification-filter-menu" class="filter-menu">
      <div class="filter-row primary-filters" aria-label="Primary filters">
        <button
          type="button"
          class="filter-chip compact"
          :class="{ active: modelValue === 'all' }"
          @click="updateFilter('all')"
        >
          All
          <span>{{ totalCount }}</span>
        </button>
        <button
          type="button"
          class="filter-chip compact unread-chip"
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

      <div v-if="sourceOptions.length" class="filter-row source-filters" aria-label="Source filters">
        <button
          v-for="option in sourceOptions"
          :key="option.value"
          type="button"
          class="filter-chip compact source-chip"
          :class="{ active: modelValue === option.value }"
          @click="updateFilter(option.value)"
        >
          {{ option.label }}
          <span>{{ option.count }}</span>
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
  </div>
</template>

<style scoped lang="scss">
.notification-filters {
  display: grid;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  border-bottom: 1px solid var(--glass-border);
  background: linear-gradient(180deg, var(--glass-bg-medium), transparent);
}

.filter-summary-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  min-width: 0;
}

.filter-menu {
  display: grid;
  gap: var(--spacing-2);
  max-height: 11rem;
  overflow-y: auto;
  padding: var(--spacing-2);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  background: rgba(var(--background-darker-rgb), 0.42);
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

.filter-menu-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-width: 0;
  min-height: 2.25rem;
  width: 100%;
  justify-content: space-between;
  padding: 0 var(--spacing-3);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  background: var(--glass-bg-subtle);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 700;
  cursor: pointer;
}

.filter-menu-toggle:hover,
.filter-menu-toggle:focus-visible {
  border-color: var(--primary-color);
  outline: none;
}

.filter-icon {
  width: 1rem;
  height: 1rem;
  stroke: currentColor;
  fill: none;
}

.active-filter-label {
  min-width: 0;
  max-width: 13rem;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.source-chip.active {
  border-color: var(--info-color);
  background: rgba(0, 180, 216, 0.12);
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

  .filter-summary-row,
  .filter-row {
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    margin-inline: calc(-1 * var(--spacing-2));
    padding-inline: var(--spacing-2);
    padding-bottom: var(--spacing-1);
    scroll-padding-inline: var(--spacing-2);
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }

  .filter-chip,
  .filter-menu-toggle {
    flex: 0 0 auto;
  }
}
</style>
