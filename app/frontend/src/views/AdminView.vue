<template>
  <div class="admin-view">
    <AdminPanel />
  </div>
</template>

<script setup lang="ts">
import AdminPanel from '../components/admin/AdminPanel.vue'
</script>

<style scoped>
.admin-view {
  min-height: 100vh;
  background: var(--color-background);
  color: var(--color-text);
  padding-top: 20px;
}
</style>
