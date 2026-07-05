<script setup lang="ts">
interface Props {
  caption?: string
  minWidth?: string
  labelledBy?: string
}

withDefaults(defineProps<Props>(), {
  minWidth: '600px',
})
</script>

<template>
  <div class="table-wrapper base-table-wrapper">
    <table class="data-table base-table" :style="{ minWidth }" :aria-labelledby="labelledBy">
      <caption v-if="caption" class="base-table-caption">{{ caption }}</caption>
      <slot />
    </table>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.base-table-wrapper {
  margin: 0;
}

.base-table-caption {
  padding: var(--spacing-3) var(--spacing-4);
  color: var(--text-secondary);
  font-size: v.$text-sm;
  text-align: left;
}
</style>
