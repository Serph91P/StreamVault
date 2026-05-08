<script setup lang="ts">
/**
 * BaseList — opinionated list primitive used as a card-stack on every
 * breakpoint. Items render as separate surfaces (no inner dividers,
 * no first/last edge artifacts) and slot whatever content the caller
 * needs. Designed as the "default list" for new views; existing tables
 * (SubscriptionsView et al.) can keep their per-view styling and adopt
 * this incrementally.
 *
 * Usage:
 *   <BaseList :items="rows" key-field="id">
 *     <template #default="{ item }">…</template>
 *   </BaseList>
 */

defineProps<{
  items: readonly unknown[]
  /** Property on each item to use as :key. Falls back to index. */
  keyField?: string
  /** Visual density: 'comfortable' (default) or 'compact'. */
  density?: 'comfortable' | 'compact'
  /** Optional aria-label for the list container. */
  ariaLabel?: string
}>()

function resolveKey(item: unknown, keyField: string | undefined, fallback: number): string | number {
  if (!keyField) return fallback
  if (item && typeof item === 'object' && keyField in (item as Record<string, unknown>)) {
    const v = (item as Record<string, unknown>)[keyField]
    if (typeof v === 'string' || typeof v === 'number') return v
  }
  return fallback
}
</script>

<template>
  <ul
    class="base-list"
    :class="{ 'is-compact': density === 'compact' }"
    :aria-label="ariaLabel"
  >
    <li
      v-for="(item, idx) in items"
      :key="resolveKey(item, keyField, idx)"
      class="base-list-item"
    >
      <slot :item="item" :index="idx" />
    </li>
    <li v-if="items.length === 0" class="base-list-empty">
      <slot name="empty">
        <span class="base-list-empty-text">No items</span>
      </slot>
    </li>
  </ul>
</template>

<style lang="scss" scoped>
.base-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.base-list.is-compact {
  gap: var(--spacing-2);
}

.base-list-item {
  padding: var(--spacing-4);
  background: var(--glass-bg-subtle, var(--background-secondary));
  border: 1px solid var(--glass-border, var(--border-color));
  border-radius: var(--radius-lg);
  transition: var(--transition-base);
}

.base-list.is-compact .base-list-item {
  padding: var(--spacing-3);
}

.base-list-item:hover {
  border-color: var(--color-primary);
}

.base-list-empty {
  padding: var(--spacing-6);
  text-align: center;
  background: transparent;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
}

.base-list-empty-text {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
</style>
