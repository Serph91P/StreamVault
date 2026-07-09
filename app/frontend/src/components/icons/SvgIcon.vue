<template>
  <svg class="svg-icon" aria-hidden="true" focusable="false">
    <use :href="iconHref" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  name: string
}>()

const iconHref = computed(() => `#icon-${props.name}`)
</script>

<style scoped>
.svg-icon {
  width: 1em;
  height: 1em;
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
}
</style>
