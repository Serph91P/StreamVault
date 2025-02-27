<script setup lang="ts">
defineProps<{
  position?: 'top' | 'right' | 'bottom' | 'left'
}>()
</script>

<template>
  <div class="tooltip-container">
    <span class="tooltip-icon">?</span>
    <div class="tooltip-content" :class="position || 'top'">
      <slot></slot>
    </div>
  </div>
</template>