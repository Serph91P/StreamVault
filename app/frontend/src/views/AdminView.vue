<template>
  <div class="page-view admin-view">
    <AdminPanel />
  </div>
</template>

<script setup lang="ts">
import AdminPanel from '../components/admin/AdminPanel.vue'
</script>

<style scoped>
.admin-view {
  /* .page-view provides padding/sizing via global styles */
  min-height: 100vh;
  background: var(--color-background);
  color: var(--color-text);
}
</style>
